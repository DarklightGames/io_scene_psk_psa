from tools.blender_versions import check_project_configuration


def test_project_configuration_is_consistent():
    problems = check_project_configuration()
    assert not problems, '\n'.join(problems)
