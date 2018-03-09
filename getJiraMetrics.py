import csv
import getpass
import json
import operator
import os
import datetime
import sys
from functools import reduce

import yaml

# https://jira.readthedocs.io/en/master/
from jira import JIRA, JIRAError


def read_config_key(key, default=None):
    try:
        if type(key) is list or type(key) is tuple:
            return reduce(operator.getitem, key, config)
        else:
            return config[key]
    except KeyError:
        return default


yaml_stream = open('getJiraMetricsConfig.yaml', 'r')
config = yaml.load(yaml_stream)

os.environ['HTTPS_PROXY'] = ''
os.environ['https_proxy'] = ''

# Pass in a tuple of coma sep strings of key names to read_config_key to get nested values
username = read_config_key(('Connection', 'Username'))
password = read_config_key(('Connection', 'Password'))

while not username or username is None:
    username = input("Please enter the Jira username: ")

while not password or password is None:
    password = getpass.getpass("Please enter the password for the Jira user: ")

auth = (username, password)
options = {
    'server': config['Connection']['Domain'],
    'basic-auth': auth
}

try:
    project_codes = ','.join(map(str, read_config_key('Projects', ())))
except TypeError as e:
    print("** Error, please check getJiraMetricsConfig.yaml has at least one project set in the Projects section")
    sys.exit(2)

status_map = read_config_key(('StatusTypes', 'StatusMap'), {})
in_process_states = read_config_key(('StatusTypes', 'InProcess'), [])
in_progress_states = read_config_key(('StatusTypes', 'InProgress'), [])
inactive_states = read_config_key(('StatusTypes', 'Inactive'), [])

try:
    jira = JIRA(options, basic_auth=auth, max_retries=0, validate=True)
except JIRAError as e:
    if e.status_code == 401:
        print("Login error, looks like your username and/or password was incorrect")
    elif e.status_code == 403:
        print("Login error, try logging into Jira in a browser as your user may need to complete a CAPTCHA")
    else:
        print("Login error, code: ", e.status_code, e.status_code)
    sys.exit(1)


def get_open_defects():
    defect_jql = read_config_key('OpenDefectJQL')
    if defect_jql is None:
        return None

    defect_types = ','.join(map(str, read_config_key(('IssueTypes', 'Defects'), ())))
    complete_states = ','.join(map(str, read_config_key(('StatusTypes', 'Closed'), ())))

    defect_jql = defect_jql.replace('{{projects}}', project_codes)
    defect_jql = defect_jql.replace('{{defects}}', defect_types)
    defect_jql = defect_jql.replace('{{complete}}', complete_states)

    all_defects = jira.search_issues(defect_jql)
    if all_defects.total <= 0:
        return None

    return all_defects


def get_cycle_time(issue_key):
    jira_issue = jira.issue(issue_key, 'self,issuetype,priority,customfield_12401', 'changelog')
    # print(json.dumps(jira_issue.raw))
    # for field_name in jira_issue.raw['fields']:
    #     print("Field:", field_name, "Value:", jira_issue.raw['fields'][field_name])

    issue_type = jira_issue.fields.issuetype
    issue_priority = jira_issue.fields.priority

    if jira_issue.fields.customfield_12401 is not None:
        class_of_service = jira_issue.fields.customfield_12401
    else:
        class_of_service = "NOT SET"

    changelog = jira_issue.changelog
    last_time = None
    time_in_status = {}

    for history in changelog.histories:
        for item in history.items:
            if item.field == 'status':
                this_time = datetime.datetime.strptime(history.created, '%Y-%m-%dT%H:%M:%S.%f%z')
                # status_col = getattr(item, 'from')  # 'from' is a reserved word so have to use getattr to get it
                status_col = item.fromString

                if status_col in status_map:
                    status_col = status_map[status_col]

                if last_time is None:
                    last_time = this_time
                else:
                    duration = this_time - last_time
                    mins_diff = divmod(duration.days * 86400 + duration.seconds, 60)[0]

                    weekend_days = 0
                    tmp = this_time
                    while tmp.date() > last_time.date():
                        if tmp.weekday() >= 5:
                            weekend_days += 1
                        tmp = tmp - datetime.timedelta(days=1)

                    non_working_mins = weekend_days * 24 * 60

                    working_mins = mins_diff - non_working_mins

                    # If someone works on a weekend, we can get -ve mins worked. This is an exception, and there's no
                    # easy way to workout how much of the weekend was worked, so lets try adding back half a day at a
                    # time until get +ve working_mins, assumption being not all weekend worked all the time (for now)
                    while working_mins <= 0:
                        working_mins += 720

                    qtr_days = divmod(working_mins, 360)[0]  # 360 mins = 1/4 of a day

                    # If > 1hr but < 1/4day worked, set to 1/4 day so stats look better
                    if qtr_days == 0 and working_mins > 59:
                        qtr_days = 1

                    full_days, qtrs = divmod(qtr_days, 4)
                    days = full_days + (qtrs * 0.25)

                    if status_col in time_in_status:
                        time_in_status[status_col] += days
                    else:
                        time_in_status[status_col] = days

                    last_time = this_time

    total = 0
    in_process = 0
    inactive = 0

    row = get_empty_return_dict()
    row['Issue'] = issue_key
    row['type'] = issue_type
    row['priority'] = issue_priority
    row['class'] = class_of_service

    for status in time_in_status:
        row[status] = time_in_status[status]

        if status in in_process_states:
            in_process += time_in_status[status]

        if status in inactive_states:
            inactive += time_in_status[status]

        if status in in_progress_states:
            total += time_in_status[status]

    row['In Process'] = in_process
    row['Inactive'] = inactive
    row['Total'] = total

    return row


def get_empty_return_dict():
    ret = {
        'Issue': '',
        'Todo': 0,
        'Ready': 0,
        'On Hold': 0,
        'In Progress': 0,
        'Ready for Code Review': 0,
        'In code review': 0,
        'Ready for Test': 0,
        'In Test': 0,
        'Ready for release': 0,
        'In Process': 0,
        'Inactive': 0,
        'Total': 0
    }

    return ret


def write_issue_row(an_issue, csv_writer):
    link = '=HYPERLINK("' + config['Connection']['Domain'] + "/browse/" + an_issue['Issue'] + '","' + an_issue['Issue']\
           + '")'
    csv_writer.writerow((link, an_issue['type'], an_issue['priority'], an_issue['class'], an_issue['Todo'],
                         an_issue['Ready'], an_issue['On Hold'], an_issue['In Progress'],
                         an_issue['Ready for Code Review'], an_issue['In code review'], an_issue['Ready for Test'],
                         an_issue['In Test'], an_issue['Ready for release'], an_issue['In Process'],
                         an_issue['Inactive'], an_issue['Total']))


def write_averages_row(issues, csv_writer):
    n = int(len(issues))
    mean_in_process = sum(an_issue['In Process'] for an_issue in issues)/n
    mean_inactive = sum(an_issue['Inactive'] for an_issue in issues)/n
    mean_total = sum(an_issue['Total'] for an_issue in issues)/n
    csv_writer.writerow(('Averages', '', '', '', '', '', '', '', '', '', '', '', '', mean_in_process, mean_inactive,
                         mean_total))
    csv_writer.writerow(('', '', '', '', '', '', '', '', '', '', '', '', '', '', 'Throughput', n))


def write_new_group_header(class_of_service=None):
    writer.writerow('')

    if class_of_service is not None:
        writer.writerow(['CLASS OF SERVICE', cos])

    writer.writerow(('Issue', 'Type', 'Priority', 'Class of Service', 'ToDo', 'Ready', 'On Hold', 'In Progress',
                     'Ready for Review', 'Code Review', 'Ready for test', 'Test', 'Ready to Release', 'In Process',
                     'Inactive', 'Total'))


from_date = None
to_date = None

if len(sys.argv) >= 2:
    try:
        from_date = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d")
        from_date = from_date.strftime("%Y-%m-%d")
        print(from_date)
    except ValueError:
        print('Invalid from date arg')
        sys.exit(1)

if len(sys.argv) >= 3:
    try:
        to_date = datetime.datetime.strptime(sys.argv[2], "%Y-%m-%d")
        to_date = to_date.strftime("%Y-%m-%d")
        print(to_date)
    except ValueError:
        print('Invalid to date arg')
        sys.exit(1)

if from_date is None:
    today = datetime.date.today()
    last_monday = today - datetime.timedelta(days=today.weekday())
    from_date = last_monday.strftime("%Y-%m-%d")

if to_date is None:
    to_date = datetime.date.today().strftime("%Y-%m-%d")

resolved_states = ','.join(map(str, read_config_key(('StatusTypes', 'Resolved'), ())))

jql = read_config_key('IssueJQL')
jql = jql.replace('{{projects}}', project_codes)
jql = jql.replace('{{resolved}}', resolved_states)
jql = jql.replace('{{from}}', "'" + from_date + "'")
jql = jql.replace('{{to}}', "'" + to_date + "'")

print("Getting Jira data and processing metrics...")

issues_done = jira.search_issues(jql)

date_string = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
outputFilename = 'cycleTime_' + date_string + '.csv'
with open(outputFilename, 'w') as fout:
    writer = csv.writer(fout, delimiter=",", quotechar='"')

    writer.writerow(['Supplier Integrations Metrics'])
    writer.writerow('')
    writer.writerow(('Date From', from_date, 'Date To', to_date))
    write_new_group_header()

    issues_done_keys = list(map(lambda x: x.key, issues_done))
    issue_cycle_data = list(map(get_cycle_time, issues_done_keys))

    for issue in issue_cycle_data:
        write_issue_row(issue, writer)

    write_averages_row(issue_cycle_data, writer)

    # Group issues by class of service
    classes = set(map(lambda a: a['class'].value, issue_cycle_data))
    issues_by_cos = {}
    for cos in classes:
        issues_by_cos[cos] = list(filter(lambda a: a['class'].value == cos, issue_cycle_data))

    for cos in issues_by_cos:
        write_new_group_header(cos)
        for iss in issues_by_cos[cos]:
            write_issue_row(iss, writer)
        write_averages_row(issues_by_cos[cos], writer)

    writer.writerow('')
    writer.writerow(['OPEN DEFECTS'])
    defects = get_open_defects()
    if defects is None:
        writer.writerow(['None'])
    else:
        for defect in defects:
            issue_stats = get_cycle_time(defect.key)
            write_issue_row(issue_stats, writer)

print("Processing complete, output saved to ", outputFilename)
