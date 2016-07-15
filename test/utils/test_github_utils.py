# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from pipeline.utils import github_utils
import mock
import os
import json

_USERNAME = 'fake_username'
_PASSWORD = 'fake_password'
_FAKE_LOCAL = 'test/fake-repos/fake-local-git-repo'
_OWNER = 'fake-owner'
_REPO = 'fake-repo'
_BRANCH = 'fake-branch'
_MESSAGE = 'fake-message'
_BASE_URL = '{0}/repos/{1}/{2}/'.format(
    github_utils._API_URL, _OWNER, _REPO)
_POST_TREE_URL = _BASE_URL + 'git/trees'
_POST_COMMIT_URL = _BASE_URL + 'git/commits'
_GET_BRANCH_URL = _BASE_URL + 'branches/{0}'.format(_BRANCH)
_GET_TREE_URL = _BASE_URL + 'git/trees/'
_PATCH_REF_URL = _BASE_URL + 'git/refs/heads/{0}'.format(_BRANCH)
_TREE_MODE = github_utils._TREE_EL_MODES['tree']
_FILE_MODE = github_utils._TREE_EL_MODES['file']
_EXEC_MODE = github_utils._TREE_EL_MODES['executable']
_FAKE_BRANCH = {'sha': 'fake-branch-sha',
                'commit': {'commit': {'tree': {'sha': 'root_sha',
                                               'full_path': '_FAKE_REMOTE'}},
                           'sha': 'fake-commit-sha'}}

# fake tree objects for remote repository
_REMOTE_TREES = {'root_sha': {'sha': 'root_sha',
                              'tree': [{'path': 'main', 'mode': _TREE_MODE,
                                        'sha': 'main_sha'}]},
                 'main_sha': {'sha': 'main_sha',
                              'tree': [{'path': 'hello.txt',
                                        'mode': _FILE_MODE,
                                        'sha': 'hello.txt_sha'}]},
                 'extra_sha': {'sha': 'extra_sha',
                               'tree': [{'path': 'bye.txt', 'mode': _FILE_MODE,
                                         'sha': 'bye.txt_sha'}]}}
EXPECTED_CALL_ARGS = [mock.call('GET', _GET_BRANCH_URL),
                      mock.call('GET', _GET_TREE_URL + 'root_sha'),
                      mock.call('GET', _GET_TREE_URL + 'main_sha'),
                      mock.call('POST', _POST_TREE_URL,
                                json.dumps({'tree': [{'path': 'blank.txt',
                                                      'mode': _FILE_MODE,
                                                      'type': 'blob',
                                                      'content': ''}]}),
                                _USERNAME, _PASSWORD),
                      mock.call(
                          'POST', _POST_TREE_URL,
                          json.dumps({'base_tree': 'main_sha',
                                      'tree': [{'path': 'subdir',
                                                'mode': _TREE_MODE,
                                                'type': 'tree',
                                                'sha': 'fake-tree-sha'},
                                               {'path': 'hello.txt',
                                                'mode': _FILE_MODE,
                                                'type': 'blob',
                                                'content': 'hello local\n'}]}),
                          _USERNAME, _PASSWORD),
                      mock.call(
                          'POST', _POST_TREE_URL,
                          json.dumps(
                              {'tree':
                               [{'path': 'executable.py',
                                 'mode': _EXEC_MODE,
                                 'type': 'blob',
                                 'content': '#!/usr/bin/env python\n'}]}),
                          _USERNAME, _PASSWORD),
                      mock.call(
                          'POST', _POST_TREE_URL,
                          json.dumps({'base_tree': 'root_sha',
                                      'tree': [{'path': 'main',
                                                'mode': _TREE_MODE,
                                                'type': 'tree',
                                                'sha': 'fake-tree-sha'},
                                               {'path': 'util',
                                                'mode': _TREE_MODE,
                                                'type': 'tree',
                                                'sha': 'fake-tree-sha'}]}),
                          _USERNAME, _PASSWORD),
                      mock.call('POST', _POST_COMMIT_URL,
                                json.dumps({'tree': 'fake-tree-sha',
                                            'parents': ['fake-commit-sha'],
                                            'message': 'fake-message'}),
                                _USERNAME, _PASSWORD),
                      mock.call('PATCH', _PATCH_REF_URL,
                                json.dumps({'force': True,
                                            'sha': 'fake-commit-sha'}),
                                _USERNAME, _PASSWORD)]


def _requests_side_effect(http_method, url, req_data=None, username=None,
                          password=None):
    """Side effect function for mocking of get_request_content"""
    if http_method == 'POST':
        if (url == _POST_TREE_URL and username == _USERNAME and
                password == _PASSWORD):
            return {'sha': 'fake-tree-sha'}
        if (url == _POST_COMMIT_URL and username == _USERNAME and
                password == _PASSWORD):
            return {'sha': 'fake-commit-sha'}
    if http_method == 'GET':
        if url == _GET_BRANCH_URL:
            return _FAKE_BRANCH
        if (len(url) >= len(_GET_TREE_URL) and
                url[:len(_GET_TREE_URL)] == _GET_TREE_URL):
            return _REMOTE_TREES[url[len(_GET_TREE_URL):]]
    if not (http_method == 'PATCH' and url == _PATCH_REF_URL and
            username == _USERNAME and password == _PASSWORD):
        raise Exception('Bad HTTP request at {0}'.format(url))


def _imm_subdirs_side_effect(curr_dir):
    """Must mock this function so order of subdirectories is known"""
    if curr_dir == _FAKE_LOCAL:
        return ['main', 'util']
    elif curr_dir == os.path.join(_FAKE_LOCAL, 'main'):
        return ['subdir']
    return []


@mock.patch('pipeline.utils.github_utils._get_immediate_subdirs',
            side_effect=_imm_subdirs_side_effect)
@mock.patch('pipeline.utils.github_utils._exec_request',
            side_effect=_requests_side_effect)
def test_github_utils_task(mock_exec_request, mock_imm_subdirs):
    github_utils.push_dir_github(_FAKE_LOCAL, _USERNAME, _PASSWORD, _OWNER,
                                 _REPO, _BRANCH, _MESSAGE)
    mock_args = mock_exec_request.call_args_list
    assert mock_args == EXPECTED_CALL_ARGS
