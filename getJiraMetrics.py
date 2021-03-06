import csv
import getpass
import json
import os
import datetime
import sys

from configFileUtils import Config

# https://jira.readthedocs.io/en/master/
from jira import JIRA, JIRAError

config_yaml = open('getJiraMetricsConfig.yaml', 'r')
config = Config(config_yaml)

os.environ['HTTPS_PROXY'] = ''
os.environ['https_proxy'] = ''

# Pass in a tuple of coma sep strings of key names to read_config_key to get nested values
username = config.read_config_key(('Connection', 'Username'))
password = config.read_config_key(('Connection', 'Password'))
server = config.read_config_key(('Connection', 'Domain'))

while not username or username is None:
    username = input("Please enter the Jira username: ")

while not password or password is None:
    password = getpass.getpass("Please enter the password for the Jira user: ")

auth = (username, password)
options = {
    'server': server,
    'basic-auth': auth
}

try:
    project_codes = ','.join(map(str, config.read_config_key('Projects', ())))
except TypeError as e:
    print("** Error, please check getJiraMetricsConfig.yaml has at least one project set in the Projects section")
    sys.exit(2)


status_map = config.read_config_key(('StatusTypes', 'StatusMap'), {})
in_process_states = config.read_config_key(('StatusTypes', 'InProcess'), [])
in_progress_states = config.read_config_key(('StatusTypes', 'InProgress'), [])
inactive_states = config.read_config_key(('StatusTypes', 'Inactive'), [])

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
    defect_jql = config.read_config_key('OpenDefectJQL')
    if defect_jql is None:
        return None

    defect_types = config.get_quoted_cs_string(('IssueTypes', 'Defects'))
    complete_states = config.get_quoted_cs_string(('StatusTypes', 'Closed'))

    defect_jql = defect_jql.replace('{{projects}}', project_codes)
    defect_jql = defect_jql.replace('{{defects}}', defect_types)
    defect_jql = defect_jql.replace('{{complete}}', complete_states)

    maxIssuesToGet = config.read_config_key('MaxIssuesToGet', 150)
    all_defects = jira.search_issues(defect_jql, maxResults=maxIssuesToGet)
    if all_defects.total <= 0:
        return None

    return all_defects


def get_closed_defects():
    defect_jql = config.read_config_key('DefectsJQL')
    if defect_jql is None:
        return None

    defect_types = config.get_quoted_cs_string(('IssueTypes', 'Defects'))
    resolved_states = config.get_quoted_cs_string(('StatusTypes', 'Resolved'))
    complete_states = config.get_quoted_cs_string(('StatusTypes', 'Closed'))

    defect_jql = defect_jql.replace('{{projects}}', project_codes)
    defect_jql = defect_jql.replace('{{defects}}', defect_types)
    defect_jql = defect_jql.replace('{{complete}}', complete_states)
    defect_jql = defect_jql.replace('{{resolved}}', resolved_states)
    defect_jql = defect_jql.replace('{{from}}', "'" + from_date + "'")
    defect_jql = defect_jql.replace('{{to}}', "'" + to_date + "'")

    maxIssuesToGet = config.read_config_key('MaxIssuesToGet', 150)
    all_defects = jira.search_issues(defect_jql, maxResults=maxIssuesToGet)
    if all_defects.total <= 0:
        return None

    return all_defects


def get_class_of_service(jira_issue):
    try:
        if jira_issue.fields.customfield_12401 is not None:
            class_of_service = jira_issue.fields.customfield_12401.value
        else:
            class_of_service = "NOT SET"
    except AttributeError:
        class_of_service = "NOT SET"

    return class_of_service


def get_work_type(jira_issue):
    try:
        if jira_issue.fields.customfield_15200 is not None:
            work_type = jira_issue.fields.customfield_15200.value
        else:
            work_type = "NOT SET"
    except AttributeError:
        work_type = "NOT SET"

    return work_type


def get_cycle_time(issue_key):
    jira_issue = jira.issue(issue_key, 'self,issuetype,priority,customfield_12401,customfield_15200,created', 'changelog')
    # print(json.dumps(jira_issue.raw))
    #for field_name in jira_issue.raw['fields']:
        #print("Field:", field_name, "Value:", jira_issue.raw['fields'][field_name])

    issue_type = jira_issue.fields.issuetype
    issue_priority = jira_issue.fields.priority

    class_of_service = get_class_of_service(jira_issue)
    work_type = get_work_type(jira_issue)

    changelog = jira_issue.changelog
    last_time = None
    last_time_flagged = None
    time_in_status = {"Flagged": 0}

    if jira_issue.fields.created is not None:
        last_time = datetime.datetime.strptime(jira_issue.fields.created, '%Y-%m-%dT%H:%M:%S.%f%z')

    for history in changelog.histories:
        for item in history.items:
            if item.field == 'status' or item.field == 'Flagged':
                this_time = datetime.datetime.strptime(history.created, '%Y-%m-%dT%H:%M:%S.%f%z')

                if item.field == 'status':
                    status_col = item.fromString
                    if status_col in status_map:
                        status_col = status_map[status_col]

                    if last_time is None:
                        last_time = this_time
                    else:
                        days = calculate_duration(last_time, this_time)

                        if status_col in time_in_status:
                            time_in_status[status_col] += days
                        else:
                            time_in_status[status_col] = days

                        if status_col not in all_statuses:
                            all_statuses[status_col] = 1
                        else:
                            all_statuses[status_col] += 1

                        last_time = this_time
                elif item.field == 'Flagged':
                    if item.toString == 'Impediment':
                        if last_time_flagged is not None:
                            print('** Error reading flagged times - we already have flag added?')
                            print('DO NOT RELY ON FLAGGED TIMES UNTIL INVESTIGATED')
                        last_time_flagged = this_time
                    elif item.fromString == 'Impediment':
                        if last_time_flagged is None:
                            print('** Error reading flagged times - no timestamp for flag added?')
                            print('DO NOT RELY ON FLAGGED TIMES UNTIL INVESTIGATED')
                        else:
                            days = calculate_duration(last_time_flagged, this_time)

                            if item.field in time_in_status:
                                time_in_status[item.field] += days
                            else:
                                time_in_status[item.field] = days

    total = 0
    in_process = 0
    inactive = 0

    row = get_empty_return_dict()
    row['Issue'] = issue_key
    row['type'] = issue_type
    row['priority'] = issue_priority
    row['class'] = class_of_service
    row['work_type'] = work_type

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


def calculate_duration(start_time, end_time):
    duration = end_time - start_time
    mins_diff = divmod(duration.days * 86400 + duration.seconds, 60)[0]

    weekend_days = 0
    tmp = end_time
    while tmp.date() > start_time.date():
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

    return days


def get_empty_return_dict():
    ret = {
        'Issue': '',
        'In Process': 0,
        'Inactive': 0,
        'Total': 0,
        'class': 'NOT SET',
        'work_type': 'NOT SET'
    }

    output_states = config.read_config_key('OutputStatusCols', [])
    for key in output_states:
        ret[key] = 0

    return ret


def write_issue_row(an_issue, csv_writer):
    link = '=HYPERLINK("' + server + "/browse/" + an_issue['Issue'] + '","' + an_issue['Issue']\
           + '")'

    keys = ['type', 'priority', 'class', 'work_type']
    keys.extend(config.read_config_key('OutputStatusCols', []))
    keys.extend(['In Process', 'Inactive', 'Total'])

    output_row = [link]
    output_row.extend(list(map(lambda x: an_issue[x], keys)))
    csv_writer.writerow(tuple(output_row))


def write_summary_rows(issues, csv_writer, cos):
    n = int(len(issues))
    if n <= 0:
        return

    sum_in_process = sum(an_issue['In Process'] for an_issue in issues)
    sum_inactive = sum(an_issue['Inactive'] for an_issue in issues)
    sum_flagged = sum(an_issue['Flagged'] for an_issue in issues)
    sum_total = sum(an_issue['Total'] for an_issue in issues)

    mean_in_process = sum_in_process / n
    mean_inactive = sum_inactive / n
    mean_flagged = sum_flagged / n
    mean_total = sum_total / n

    output_cols = list(config.read_config_key('OutputStatusCols', []))
    mylist = list([''] * (len(output_cols) + 3))
    mylist.extend(['Averages'])
    if "Flagged" in output_cols:
        mylist.extend([mean_flagged])
    mylist.extend([mean_in_process, mean_inactive, mean_total])
    csv_writer.writerow(mylist)

    totalsList = list([''] * (len(output_cols) + 3))
    totalsList.extend(['Totals'])
    if "Flagged" in output_cols:
        totalsList.extend([sum_flagged])
    totalsList.extend([sum_in_process, sum_inactive, sum_total])
    csv_writer.writerow(totalsList)

    mylist = [''] * (len(output_cols) + 6)
    mylist.extend(['Throughput', n])
    csv_writer.writerow(mylist)


def write_new_group_header(class_of_service=None):
    writer.writerow('')

    if class_of_service is not None:
        writer.writerow(['CLASS OF SERVICE', cos])

    static_headers = ('Issue', 'Type', 'Priority', 'Class of Service', 'Work Type')
    static_headers_postfix = ('In Process', 'Inactive', 'Total')
    status_cols = tuple(config.read_config_key('OutputStatusCols', []))
    headers = static_headers + (status_cols) + static_headers_postfix
    writer.writerow(headers)


def get_issue_keys(issues):
    return list(map(lambda x: x.key, issues))


def get_issue_cycle_data(issue_keys):
    return list(map(get_cycle_time, issue_keys))


def output_issues(issue_cycle_data, writer, type=None):
    if type is None:
        type = 'everything'

    for issue in issue_cycle_data:
        write_issue_row(issue, writer)

    write_summary_rows(issue_cycle_data, writer, type)


def output_group_header(name=""):
    writer.writerow('')
    writer.writerow([name])
    write_new_group_header()


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

resolved_states = config.get_quoted_cs_string(('StatusTypes', 'Resolved'))
complete_states = config.get_quoted_cs_string(('StatusTypes', 'Closed'))

jql = config.read_config_key('IssueJQL')
jql = jql.replace('{{projects}}', project_codes)
jql = jql.replace('{{resolved}}', resolved_states)
jql = jql.replace('{{complete}}', complete_states)
jql = jql.replace('{{from}}', "'" + from_date + "'")
jql = jql.replace('{{to}}', "'" + to_date + "'")

print("\nUsing the following JQL to get issues\n", jql)
print("Getting Jira data and processing metrics...")

repTitle = config.read_config_key('ReportTitle', 'Team Metrics')
maxIssuesToGet = config.read_config_key('MaxIssuesToGet', 150)
issues_done = jira.search_issues(jql, maxResults=maxIssuesToGet)
all_statuses = {}

date_string = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
outputFilename = 'cycleTime_' + date_string + '.csv'
with open(outputFilename, 'w') as fout:
    writer = csv.writer(fout, delimiter=",", quotechar='"')

    writer.writerow([repTitle])
    writer.writerow('')
    writer.writerow(('Date From', from_date, 'Date To', to_date))
    write_new_group_header()

    issues_done_keys = get_issue_keys(issues_done)
    issue_cycle_data = get_issue_cycle_data(issues_done_keys)
    output_issues(issue_cycle_data, writer, 'everything')

    # Group issues by class of service
    classes = set(map(lambda a: a['class'], issue_cycle_data))
    issues_by_cos = {}
    for cos in classes:
        issues_by_cos[cos] = list(filter(lambda a: a['class'] == cos, issue_cycle_data))

    for cos in issues_by_cos:
        write_new_group_header(cos)
        for iss in issues_by_cos[cos]:
            write_issue_row(iss, writer)
        write_summary_rows(issues_by_cos[cos], writer, cos)

    output_group_header('OPEN DEFECTS')
    defects = get_open_defects()
    if defects is None:
        writer.writerow(['None'])
    else:
        defect_keys = get_issue_keys(defects)
        defect_data = get_issue_cycle_data(defect_keys)
        output_issues(defect_data, writer, 'OpenDefects')

    output_group_header('DEFECTS (closed)')
    defects = get_closed_defects()
    if defects is None:
        writer.writerow(['None'])
    else:
        defect_keys = get_issue_keys(defects)
        defect_data = get_issue_cycle_data(defect_keys)
        output_issues(defect_data, writer, 'ClosedDefects')

print("Processing complete, output saved to ", outputFilename)

print("\n", "Found the following statues in the processed issues:")
print(all_statuses)
print("\n")

jql = config.read_config_key('ReleasesJQL')
jql = jql.replace('{{from}}', "'" + from_date + "'")
jql = jql.replace('{{to}}', "'" + to_date + "'")

print("\nUsing the following JQL to get release issues\n", jql)
print("Searching for releases...")
release_issues = jira.search_issues(jql, maxResults=maxIssuesToGet)
releases = 0
found_in_rel = False
project_codes_tuple = tuple(config.read_config_key('Projects', ()))

print("Scanning found releases for your team/projects tickets as linked issues...")
for issueId in release_issues:
    rel = jira.issue(issueId)
    if (rel.fields.issuelinks):
        for link in rel.fields.issuelinks:
            if hasattr(link, "outwardIssue"):
                linkedIssue = link.outwardIssue
            elif hasattr(link, "inwardIssue"):
                linkedIssue = link.inwardIssue
            else:
                linkedIssue = None

            if linkedIssue is not None:
                 try:
                     linked_issue_key = jira.issue(linkedIssue).key
                     if linked_issue_key.startswith(project_codes_tuple):
                         releases += 1
                         found_in_rel = True
                         print(rel)
                         break
                 except (JIRAError, TypeError, AttributeError):
                     print(json.dumps(rel.raw))

print ("Releases for team: " + str(releases))
