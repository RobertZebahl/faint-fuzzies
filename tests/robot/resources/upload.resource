*** Settings ***
Documentation   Support for testing "upload" without a real host, rsync, sshpass or OS keyring - see
...             fixtures/upload: bin/rsync and bin/sshpass are fake executables, fake_keyring_backend.py is a
...             keyring backend selected via PYTHON_KEYRING_BACKEND (keyring's own documented test mechanism),
...             and each home_* folder is a HOME directory holding one config.toml scenario (config.CONFIG_PATH
...             is fixed under $HOME, so the only way to point it at a fixture is to run with $HOME overridden).
Library         Process
Library         OperatingSystem
Resource        cli.resource


*** Variables ***
${UPLOAD_FIXTURES}     ${FIXTURES}${/}upload
${TOOLS_BIN}           ${UPLOAD_FIXTURES}${/}bin
${SSHPASS_LOG}         ${OUTPUT DIR}${/}fake_sshpass.log


*** Keywords ***
Run Upload
    [Documentation]    Runs "upload" with $home as the config file's home directory, $tools_on_path controlling
    ...    whether the fake rsync/sshpass are reachable, and $password controlling what the fake keyring
    ...    backend returns (unset: no password stored, as if "keyring set" was never run). The fake sshpass's
    ...    own log (what it was actually called with, if it ran at all) is cleared first and left at
    ...    ${SSHPASS_LOG} for Sshpass Log Should Contain / Sshpass Should Not Have Run to check afterwards.
    [Arguments]    ${output_dir}    ${home}    @{options}    ${tools_on_path}=${TRUE}    ${password}=${NONE}
    ...    ${bin_dir}=${TOOLS_BIN}
    ${real_bin}=    Evaluate    os.path.dirname(sys.executable)    modules=os,sys
    ${path}=    Set Variable If    ${tools_on_path}    ${bin_dir}${:}${real_bin}    ${real_bin}
    Remove File    ${SSHPASS_LOG}
    &{env}=    Create Dictionary
    ...    env:HOME=${home}
    ...    env:PATH=${path}
    ...    env:PYTHONPATH=${UPLOAD_FIXTURES}
    ...    env:PYTHON_KEYRING_BACKEND=fake_keyring_backend.FakeKeyring
    ...    env:FAKE_SSHPASS_LOG=${SSHPASS_LOG}
    IF    $password is not None
        Set To Dictionary    ${env}    env:FAKE_KEYRING_PASSWORD=${password}
    END
    ${result}=    Run Process    ${CLI}    upload    --output-dir    ${output_dir}    @{options}    &{env}
    RETURN    ${result}

Sshpass Log Should Contain
    [Documentation]    Checks that the fake sshpass was actually run and received every one of the given
    ...    arguments (each on its own line - see fixtures/upload/bin/sshpass).
    [Arguments]    @{expected}
    File Should Exist    ${SSHPASS_LOG}
    ${content}=    Get File    ${SSHPASS_LOG}
    FOR    ${item}    IN    @{expected}
        Should Contain    ${content}    ${item}
    END

Sshpass Should Not Have Run
    File Should Not Exist    ${SSHPASS_LOG}
