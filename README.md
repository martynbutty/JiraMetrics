# JiraMetrics
A Python script to get metrics like throughput and cycletime from Jira. Output data is written to a spreadsheet in CSV format.

If you've every validated the output from Jira's control report, you may have noticed the cycle time isn't quite as you expect, especially if you've every changed your projects workflw to add/remove or rename states. 
This seems to be because behind the screnes, Jira creates new states even for a simple case change of an existing state, which can then lead to the old states not being included in the cycle time.

Additionally, it's not easy (or even possible?) to export the data of the control report into a spreadsheet for later analysis or presentation etc.

## Setup
* Clone the repo
* (Optional) create and activate a [virtual environment](https://docs.python.org/3/tutorial/venv.html)
* Install the dependencies
  * The easiest way is to `$ pip install -r requirements.txt`
  * Alternatively, `pip install` the following
    * `$ pip install pyyaml`
    * `$ pip install jira`

## Configuration
Copy the example configuration file and edit the setting within to match your requirements
```
cp getJiraMetricsConfig.yaml.example getJiraMetricsConfig.yaml
```

If username or password are not set in your configuration file, you will be prompted for these (without showing the characters of the password where possible)

## Running the script
The script will execute the JQL in `getJiraMetricsConfig.yaml` to find issues between two dates.

Run the script without any arguments to use a time period from the most recent Monday, until today

```
$ python3 getJiraMetrics.py
```

If you want a specific from date, pass from date as the first argument to the script in the format "YYY-MM-DD". This will look for issues between the from date, and today:
```
$ python3 getJiraMetrics.py 2018-01-01
```

and if you want to also specify and end date, add that as the second argument
```
$ python3 getJiraMetrics.py 2018-01-01 2019-01-31
```

The script will output the data to a CSV file in the current directory. The script will detail the filename at the end of its run.
