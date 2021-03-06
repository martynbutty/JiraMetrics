# JiraMetrics
A Python script to get metrics like cycletime and throughput from Jira. Output data is written to a spreadsheet in CSV format.

If you've ever validated the output from Jira's control report, you may have noticed the cycle time isn't quite as you expect, especially if you've changed your projects workflow to add, remove or rename states. 
This seems to be because behind the scenes, Jira creates new states even for a simple case change of an existing states name, which can then lead to the old states not being included in the cycle time.

Additionally, it's not easy (or even possible?) to export the data of the control report into a spreadsheet for later analysis or presentation etc.

Finally, a summary of the data can also be persisted to a database. This will allow you to perform things like week on week comparisons, graphs etc.

## Dockerised run
If you are familiar with Docker, you can now run the script using Docker so you don't have to install and configure Python3 etc.
* Clone the repo
* Complete the [Configuration](#configuration) section setup below
* Run the container without any arguments to use a time period from the most recent Monday, until today
```
$ docker-compose up
```
* If you want to run the script for a specific date range, run as follows (see [Running the Script](#running-the-script) section below for argument details)
```
$docker-compose run jira-metrics 2018-09-01 2018-10-10
```
* The script will generate an output csv file in the current working directory on your host machine


## Setup
* Clone the repo
* (Optional) create and activate a [virtual environment](https://docs.python.org/3/tutorial/venv.html)
* Install the dependencies
  * The easiest way is to `$ pip install -r requirements.txt`
  * Alternatively, `pip install` the following
    * `$ pip install pyyaml`
    * `$ pip install jira`
* If you want to save summary data to a DB;
  * Create your schema in a suitable instance that this code can connect to
  * Apply the schema.sql file to create the DB table
  * Add the MySQL connection details to your getJiraMetricsConfig.yaml (details in the .example file)

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
