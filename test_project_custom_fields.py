import inspect
import json
import pathlib
import random
import string
import subprocess
import unittest
import yaml

from CheckmarxPythonSDK.CxRestAPISDK import CustomFieldsAPI
from CheckmarxPythonSDK.CxRestAPISDK import ProjectsAPI

class Config:

    def __init__(self, filename):

        with open(filename, 'r') as f:
            self.data = yaml.load(f, Loader=yaml.Loader)


    def update_config(self, config):

        config['checkmarx']['base-url'] = self.data['checkmarx']['base-url']
        config['checkmarx']['username'] = self.data['checkmarx']['username']
        config['checkmarx']['password'] = self.data['checkmarx']['password']

        return config


def run_cxflow(cxflow_version, config, project_name, extra_args=[]):
    """Runs CxFlow"""

    print(f'Running CxFlow version {cxflow_version}')

    with open('application.yml', 'w') as f:
        f.write(yaml.dump(config, default_flow_style=False))

    args = [
        'java',
        '-jar',
        f'cx-flow-{cxflow_version}.jar',
        '--scan',
        f'--cx-project={project_name}'
    ]

    for extra_arg in extra_args:
        args.append(extra_arg)

    print(f'Command: {" ".join(args)}')
    proc = subprocess.run(args, capture_output=True)
    print(f'stdout: {proc.stdout.decode("UTF-8")}')
    print(f'stderr: {proc.stderr.decode("UTF-8")}')
    return proc.returncode


class TestCustomJiraSummaries(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestCustomJiraSummaries, self).__init__(*args, **kwargs)
        self.config = Config('config.yml')
        self.base_cx_flow_config = {
            'cx-flow': {
                'bug-tracker': 'WAIT',
                'bug-tracker-impl': ['Csv', 'Jira']
            },
            'logging': {
                'file': {
                    'name': 'cx-flow.log'}
                ,
                'level': {
                    'com': {
                        'checkmarx': {
                            'flow': 'DEBUG',
                            'sdk': 'DEBUG'
                        }
                    }
                }
            },
            'checkmarx': {
                'version': 9.2,
                'client-secret': '014DF517-39D1-4453-B7B3-9930C563627C',
                'url': '${checkmarx.base-url}/cxrestapi',
                'multi-tentant': False,
                'incremental': True,
                'scan-preset': 'Checkmarx Default',
                'configuration': 'Default Configuration',
                'team': '/CxServer',
                'portal-url': '${checkmarx.base-url}/cxwebinterface/Portal/CxWebService.asmx',
                'sdk-url': '${checkmarx.base-url}/cxwebinterface/SDK/CxSDKWebService.asmx',
                'portal-wsdl': '${checkmarx.base-url}/Portal/CxWebService.asmx?wsdl',
                'sdk-wsdl': '${checkmarx.base-url}/SDK/CxSDKWebService.asmx?wsdl'
            }
        }

        self.custom_fields_api = CustomFieldsAPI()
        self.projects_api = ProjectsAPI()

        self.custom_fields = self.custom_fields_api.get_all_custom_fields()

    def setUp(self):

        self.cx_flow_config = self.config.update_config(self.base_cx_flow_config)
        self.project_id = None

    def tearDown(self):

        if self.project_id:
            print(f'Deleting project {self.project_id}')
            self.projects_api.delete_project_by_id(self.project_id)

        cxConfig = pathlib.Path("cx.config")
        if cxConfig.exists():
            print(f'Deleting {cxConfig}')
            cxConfig.unlink()

    def test_cmdline(self):

        project_name = self.random_string(10)
        project_id = self.get_project(project_name)
        self.assertIsNone(project_id)
        extra_args = ['--f=.', '--app=App']
        expected = {}
        for custom_field in self.custom_fields:
            value = self.random_string(10)
            expected[custom_field.name] = value
            extra_args.append(f'--project-custom-field={custom_field.name}:{value}')

        self.common(project_name, extra_args, expected)

    def test_config_as_code(self):

        project_name = self.random_string(10)
        project_id = self.get_project(project_name)
        self.assertIsNone(project_id)
        extra_args = ['--f=.', '--app=App']
        expected = {}
        config = {
            'version': 1.0,
            'customFields': {
            }
        }
        tmp = []
        for custom_field in self.custom_fields:
            value = self.random_string(10)
            expected[custom_field.name] = value
            config['customFields'][custom_field.name] = value

        with open('cx.config', 'w') as f:
            json.dump(config, f)

        self.common(project_name, extra_args, expected)

    def common(self, project_name, extra_args, expected):

        self.assertEqual(0, run_cxflow(self.config.data['cx-flow']['version'],
                                       self.cx_flow_config,
                                       project_name,
                                       extra_args))
        self.project_id = self.get_project(project_name)
        self.assertIsNotNone(self.project_id)
        project = self.projects_api.get_project_details_by_id(self.project_id)
        actual = {}
        for custom_field in project.custom_fields:
            actual[custom_field.name] = custom_field.value
        self.assertEqual(expected, actual)

    def compare_issues(self, expected, actual):

        for key in ['description', 'labels', 'priority', 'application',
                    'category', 'cwe']:
            self.assertEqual(expected[key], actual[key], key)

    def random_string(self, length):

        return ''.join(random.choices(string.ascii_lowercase, k=length))

    def get_project(self, project_name):

        return self.projects_api.get_project_id_by_project_name_and_team_full_name(project_name, self.cx_flow_config['checkmarx']['team'])


if __name__ == '__main__':
    unittest.main()
