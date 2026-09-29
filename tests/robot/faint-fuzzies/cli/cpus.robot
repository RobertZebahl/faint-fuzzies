*** Settings ***
Documentation       How many CPUs the program uses for work on several threads: what the machine has and allows, less
...                 the limit of a container (`docker run --cpus=2` sets a quota that the CPU count does not show).
...                 Nothing is a fixed number.
Library             ../../libraries/CpuChecks.py


*** Test Cases ***
The Machine Decides
    ${cpus}=    Cpus Of The Machine
    ${logical}=    Logical Cpus
    Should Be True    1 <= ${cpus} <= ${logical}

No Quota Changes Nothing
    ${machine}=    Cpus Of The Machine
    ${v2}=    Cpus With Cgroup    v2=max 100000
    ${v1}=    Cpus With Cgroup    v1_quota=-1
    Should Be Equal As Integers    ${v2}    ${machine}
    Should Be Equal As Integers    ${v1}    ${machine}

A Quota Of A Container Limits It
    [Documentation]    2 CPUs of quota (200000 of 100000), 1.5 rounds up to 2, and at least 1 whatever the quota is.
    ${machine}=    Cpus Of The Machine
    ${two}=    Cpus With Cgroup    v2=200000 100000
    ${one_and_a_half}=    Cpus With Cgroup    v2=150000 100000
    ${tiny}=    Cpus With Cgroup    v2=10000 100000
    ${old}=    Cpus With Cgroup    v1_quota=200000
    Should Be Equal As Integers    ${two}    ${{min(${machine}, 2)}}
    Should Be Equal As Integers    ${one_and_a_half}    ${{min(${machine}, 2)}}
    Should Be Equal As Integers    ${tiny}    1
    Should Be Equal As Integers    ${old}    ${{min(${machine}, 2)}}

A Quota Above The Machine Does Not Add CPUs
    ${machine}=    Cpus Of The Machine
    ${many}=    Cpus With Cgroup    v2=6400000 100000
    Should Be Equal As Integers    ${many}    ${machine}

A Quota That Cannot Be Read Is Ignored
    ${machine}=    Cpus Of The Machine
    ${garbage}=    Cpus With Cgroup    v2=abc def
    ${empty}=    Cpus With Cgroup    v2=${EMPTY}
    Should Be Equal As Integers    ${garbage}    ${machine}
    Should Be Equal As Integers    ${empty}    ${machine}
