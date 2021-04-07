from flask import Flask

import pandas as pd
import os

import build_logs as bl
import project as pr

app = Flask(__name__)

@app.route("/")
def index():
    return "Open Projections"

@app.route('/build/<string:date_string>')
def build(date_string):
    if len(date_string) == 10:
        bl.build_daily_gamelogs(date_string)
    elif len(date_string) == 7:
        bl.build_monthly_gamelogs(date_string[:4], date_string[5:7])
    else:
        bl.build_yearly_gamelogs(date_string)
    bl.combine_gamelogs()
    return "Built " + date_string

@app.route('/project/<string:date_string>')
def project(date_string):
    pr.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/<string:date_string>/')
def view(date_string):
    filepath = os.path.dirname(__file__)
    batting_file = filepath + "\\projections\\" + date_string + "-batting.csv"
    df = pd.read_csv(batting_file, index_col=None, header=0)
    return df.to_html()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)