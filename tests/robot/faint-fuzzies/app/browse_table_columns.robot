*** Settings ***
Documentation       The Browse page's tables draw each row from a template (ui/browse.py: _OBJECT_ROW_BODY,
...                 _SESSION_ROW_BODY) whose cells must match the table's columns one for one, in order: a
...                 missing cell once put the session list's object count under "Seeing". The session list
...                 shows no SQM column (SQM stays in an observation's conditions text).
Library             Collections
Library             ../../libraries/BrowseTableColumnsChecks.py


*** Test Cases ***
Every Row Template Draws One Cell Per Column In Column Order
    FOR    ${table}    IN    objects    sessions
        ${columns}=    Column Names    ${table}
        ${rows}=    Row Template Cell Keys    ${table}
        Should Not Be Empty    ${rows}
        FOR    ${keys}    IN    @{rows}
            Lists Should Be Equal    ${keys}    ${columns}    msg=${table} row template
        END
    END

The Session List Has No SQM Column
    ${labels}=    Column Labels    sessions
    List Should Not Contain Value    ${labels}    SQM

Each Session Value Is Shown Under Its Own Header
    ${cells}=    Session List Cells    17    BORTLE=4    NELM=6.2    SQM=21.3    SQML=20.8    SEEING=3/5
    Should Be Equal    ${cells}[Bortle]    4
    Should Be Equal    ${cells}[NELM]    6.2
    Should Be Equal    ${cells}[SQML]    20.8
    Should Be Equal    ${cells}[Seeing]    3/5
    Should Be Equal    ${cells}[Objects]    17
    Should Be Equal    ${cells}[Location]    Home
