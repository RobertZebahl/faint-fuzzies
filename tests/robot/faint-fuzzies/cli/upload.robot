*** Settings ***
Documentation   "upload" (see cli.py, upload.py): sends a built website to its host over rsync/ssh, authenticated
...             with a password from the OS keyring, wrapped by sshpass since the host has no SSH key. No real
...             host, rsync, sshpass or keyring is involved - see resources/upload.resource.
Resource        ../../resources/upload.resource
Library         ../../libraries/UploadLineChecks.py


*** Test Cases ***
A Successful Upload Runs Sshpass With The Expected Rsync Command
    [Documentation]    Fixture "upload/home_valid": host example.test, user testuser, remote_path
    ...    /var/www/faint-fuzzies, port 2222. No --delete or --dry-run: neither flag reaches sshpass.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_valid
    ${result}=    Run Upload    ${site}    ${home}    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Sshpass Log Should Contain    -e    rsync    -avL    ssh -p 2222    ${site}${/}    testuser@example.test:/var/www/faint-fuzzies
    ...    SSHPASS=secret123
    ${content}=    Get File    ${SSHPASS_LOG}
    Should Not Contain    ${content}    --delete

--delete And --dry-run Are Passed On To Rsync
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_valid
    ${result}=    Run Upload    ${site}    ${home}    --delete    --dry-run    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Sshpass Log Should Contain    --delete    -n

--checksum Is Opt In And Passed On To Rsync As --checksum
    [Documentation]    Off by default (change detection is rsync's own size/time quick check); given, it adds
    ...    --checksum to compare file contents instead.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_valid
    ${result}=    Run Upload    ${site}    ${home}    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${content}=    Get File    ${SSHPASS_LOG}
    Should Not Contain    ${content}    --checksum
    ${result}=    Run Upload    ${site}    ${home}    --checksum    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Sshpass Log Should Contain    --checksum

exclude Is Passed On To Rsync As --exclude, With Or Without --delete
    [Documentation]    Fixture "upload/home_exclude" sets exclude = ["logs/"] - a directory the host itself
    ...    writes into, alongside the site, that --delete must never remove. Passed on every upload, not only
    ...    with --delete, so a plain upload never overwrites it either.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_exclude
    ${result}=    Run Upload    ${site}    ${home}    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Sshpass Log Should Contain    --exclude=logs/
    ${result}=    Run Upload    ${site}    ${home}    --delete    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Sshpass Log Should Contain    --exclude=logs/    --delete

--delete Is Refused When remote_path Is Empty Or "/"
    [Documentation]    Fixture "upload/home_delete_guard" sets remote_path to "/" - a config typo that would
    ...    otherwise turn --delete into wiping the whole remote account. Sshpass never runs.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_delete_guard
    ${result}=    Run Upload    ${site}    ${home}    --delete    password=secret123
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    remote_path
    Sshpass Should Not Have Run

confirm_delete_root Lifts The Guard For remote_path "/"
    [Documentation]    Fixture "upload/home_delete_root_confirmed" sets remote_path to "/" AND
    ...    confirm_delete_root = true: a chrooted account whose own root genuinely is the site root, not a
    ...    typo. --delete now reaches sshpass.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_delete_root_confirmed
    ${result}=    Run Upload    ${site}    ${home}    --delete    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Sshpass Log Should Contain    --delete    testuser@example.test:/

confirm_delete_root Lifts The Guard For An Empty remote_path Too
    [Documentation]    Fixture "upload/home_delete_root_confirmed_empty" sets confirm_delete_root = true with
    ...    remote_path = "" (not "/"): an account whose home directory already is the site root, not a typo.
    ...    --delete now reaches sshpass, the same as for remote_path = "/" above.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_delete_root_confirmed_empty
    ${result}=    Run Upload    ${site}    ${home}    --delete    password=secret123
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Sshpass Log Should Contain    --delete    testuser@example.test:

Upload Needs A Config File
    [Documentation]    Fixture "upload/home_no_config" has no ~/.config/faint-fuzzies/config.toml at all.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_no_config
    ${result}=    Run Upload    ${site}    ${home}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    config file
    Sshpass Should Not Have Run

Upload Needs Host User And remote_path In The Config
    [Documentation]    Fixture "upload/home_missing_field" has an [upload] table without "user".
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_missing_field
    ${result}=    Run Upload    ${site}    ${home}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    user

Upload Needs port To Be An Integer
    [Documentation]    Fixture "upload/home_bad_port" has port = "not-a-number".
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_bad_port
    ${result}=    Run Upload    ${site}    ${home}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    port

Upload Needs exclude To Be A List Of Strings
    [Documentation]    Fixture "upload/home_bad_exclude" has exclude = "logs/" (a plain string, not a list).
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_bad_exclude
    ${result}=    Run Upload    ${site}    ${home}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    exclude

Upload Fails Clearly When Sshpass Is Missing
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_valid
    ${result}=    Run Upload    ${site}    ${home}    tools_on_path=${FALSE}    password=secret123
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    sshpass not found
    Sshpass Should Not Have Run

Upload Fails Clearly When Rsync Is Missing
    [Documentation]    Fixture "upload/bin_sshpass_only" has a fake sshpass but no rsync at all, so the sshpass
    ...    check passes but the rsync one does not - sshpass still never actually runs, since upload.py checks
    ...    both tools are present before running anything.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_valid
    ${bin}=    Fixture    upload/bin_sshpass_only
    ${result}=    Run Upload    ${site}    ${home}    password=secret123    bin_dir=${bin}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    rsync not found
    Sshpass Should Not Have Run

Upload Needs A Password In The Keyring
    [Documentation]    $password is not given, so the fake keyring backend returns None for every username, as
    ...    if "keyring set faint-fuzzies testuser" had never been run.
    ${site}=    Fixture    upload/site
    ${home}=    Fixture    upload/home_valid
    ${result}=    Run Upload    ${site}    ${home}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    keyring set faint-fuzzies testuser
    Sshpass Should Not Have Run

Upload Needs An Existing Output Directory
    ${home}=    Fixture    upload/home_valid
    ${result}=    Run Upload    ${OUTPUT DIR}${/}does_not_exist    ${home}    password=secret123
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    does not exist
    Sshpass Should Not Have Run

With on_line, Rsync's Output Is Relayed Line By Line
    [Documentation]    on_line is only ever given by the app's Site page (see ui/site.py), never by this CLI
    ...    command - checked directly against upload_site itself, since the CLI's own subprocess-level tests
    ...    above never pass it.
    ${result}=    Upload Lines Received
    Should Be Equal    ${result}[lines]    ${{['first line', 'second line']}}
    Should Be Equal As Integers    ${result}[exit_code]    0
