from flask import Flask, Response, redirect, request, render_template

import pandas as pd
import json
from datetime import datetime

import build_logs
import blyleven as project2
import campanella as project3

app = Flask(__name__, static_folder="assets")

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/stats/<int:year>', methods=['PUT'])
def put_year_stats(year):
    build_logs.build_yearly_gamelogs(year)
    return "Built logs for " + str(year)

@app.route('/stats/<int:year>/<int:month>', methods=['PUT'])
def put_month_stats(year, month):
    build_logs.build_monthly_gamelogs(year, month)
    return "Built logs for " + str(year) + "-" + str(month)

@app.route('/stats/<int:year>/<int:month>/<int:day>', methods=['PUT'])
def put_day_stats(year, month, day):
    date_string = str(year) + "-" + str(month).zfill(2) + "-" + str(day).zfill(2)
    build_logs.build_daily_gamelogs(date_string)
    return "Built logs for " + date_string

@app.route('/projections/<string:date_string>', methods=['PUT'])
def put_projections(date_string):
    project2.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/projections/', methods=['GET'])
def get_latest_projections():
    return redirect('/projections/2022-04-01')

@app.route('/projections/<string:date_string>', methods=['GET'])
def get_projections(date_string):

    batting_df = project3.load_projection(date_string, True)
    pitching_df = project3.load_projection(date_string, False)

    if "csv" in request.args:
        csv_type = request.args["csv"]
    else:
        csv_type = None

    if csv_type == "batting":
        return Response(batting_df.to_csv(index=False), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=" + date_string + "Batting.csv"})
    elif csv_type == "pitching":
        return Response(pitching_df.to_csv(index=False), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=" + date_string + "Pitching.csv"})

    numeric_cols = batting_df.select_dtypes(include="number")
    batting_df[numeric_cols.columns] = numeric_cols.astype(int)
    numeric_cols = pitching_df.select_dtypes(include="number")
    pitching_df[numeric_cols.columns] = numeric_cols.astype(int)

    batting_html = batting_df.to_html(classes="table is-hoverable sortable", index=False)
    pitching_html = pitching_df.to_html(classes="table is-hoverable sortable", index=False)

    d = datetime(2020, 6, 1)

    dates = []
    while d < datetime.today():
        dates.append(d)

        if d.month == 12:
            d = datetime(d.year + 1, 1, 1)
        else:
            d = datetime(d.year, d.month + 1, 1)
    
    preseason_date = datetime(2022, 4, 1)

    if not preseason_date in dates:
        dates.append(preseason_date)

    selected_date = datetime.strptime(date_string, "%Y-%m-%d")

    return render_template("projections.html", batting=batting_html, pitching=pitching_html, dates=dates, selected_date=selected_date)


@app.route('/v3/projections/<string:date_string>', methods=['PUT'])
def put_v3_projections(date_string):
    project3.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/v3/projections/<string:date_string>', methods=['GET'])
def get_v3_projections(date_string):
    if (request.args.get("type") == "batting"):
        is_batting = True
    elif (request.args.get("type") == "pitching"):
        is_batting = False
    else:
        return "Error: type must be batting or pitching."

    df = project3.load_projection(date_string, is_batting)
    return df.to_json(orient="records")

@app.route('/v3/projections/', methods=['GET'])
def get_v3_player_projections():
    if 'playerId' in request.args:
        player_id = int(request.args['playerId'])
    else:
        return "Error: No playerId provided. Please specify an (MLBAM) id."

    data = {}

    bat = pd.DataFrame()
    bat = project3.load_player_projections(player_id, True)
    data["batting"] = bat.to_dict("records")

    pit = pd.DataFrame()
    pit = project3.load_player_projections(player_id, False)
    data["pitching"] = pit.to_dict("records")

    return json.dumps(data)

    
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)