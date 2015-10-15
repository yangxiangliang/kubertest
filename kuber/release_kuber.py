from git import Repo

import subprocess
import yaml
import re
import config
import sys
import logging
import os


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s', '%Y-%m-%d-%H:%M:%S'  # NOQA
))
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(handler)
log = logging.getLogger(__name__)


def release_kuber(context, app, version):
    # check whether the app belongs to the context
    if app not in config.app_dict.get(context, []):
        log.error('Provided app does not belong to the context')
        return

    try:
        # # check whether a container with app name and provided version number exists
        # container_tags = subprocess.check_output(['gsutil', 'ls', '{}/{}'.format(config.gs_path_to_app, app)])
        # container_exist = False
        #
        # for tag in container_tags.split('\n'):
        #     # tag sample:
        #     # gs://artifacts.sojern-platform.appspot.com/containers/repositories/library/applier/tag_2.3.11
        #     version_list = re.findall('\d+\.\d+\.\d+', tag.split('/')[-1])
        #     if version_list and version_list[0] == version:
        #         container_exist = True
        #         break
        #
        # if not container_exist:
        #     log.error('The container with provided app and version number does not exist')
        #     return

        git = Repo('{}/..'.format(os.getcwd())).git
        git.checkout('master')
        git.pull()

        # modify app.yml file with new version
        yaml_file = '{}.yml'.format(app)

        with open(yaml_file) as f:
            yaml_dict = yaml.load(f)

        _update_yaml_file(yaml_dict, version)

        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_dict, f, default_flow_style=False)

        # get replication controller name, sample output of this command:
        # CONTROLLER              CONTAINER (S)     IMAGES            SELECTOR     REPLICAS
        # backend-controller      applier           applier_2.3.11    applier      3
        rc_name = subprocess.check_output(['kubectl', '--context={}'.format(context), 'get', 'rc',
                                           '--selector=run={}'.format(app)]).split('\n')[1].split()[0]

        print 'controller name:', rc_name
        # run rolling update
        exit_code = subprocess.call(['kubectl', '--context=vagrant', 'rolling-update',
                                     '{}'.format(rc_name), '-f', yaml_file])

        # if rolling update succeeds, commit changes in Git repo and push back to master
        if exit_code == 0:
            log.info('Rolling update {} to {} successfully'.format(app, version))
            git.add(yaml_file)
            git.commit(m='bump {} to {}'.format(app, version))
            git.push()
        else:
            log.error('Errors in rolling update command, exit code:{}'.format(exit_code))
            git.checkout('.')

    except Exception as e:
        log.exception('Exception:{}'.format(e))


def _update_yaml_file(yaml_dict, version):
    # replace any version format substring with new version number
    if not isinstance(yaml_dict, dict):
        return
    for key, value in yaml_dict.iteritems():
        if isinstance(value, list):
            for item in value:
                _update_yaml_file(item, version)
        elif isinstance(value, dict):
            _update_yaml_file(value, version)
        elif isinstance(value, str):
            substr_match = re.search('\d+\.\d+\.\d+', value)
            if substr_match:
                start, end = substr_match.span()
                yaml_dict[key] = value[:start] + version + value[end:]

if __name__ == '__main__':
    # argv order should be: context name, application name, version number
    release_kuber(sys.argv[1], sys.argv[2], sys.argv[3])
