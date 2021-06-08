from flask import Flask, request

import pandas

import build_logs
import project

app = Flask(__name__)

@app.route("/")
def index():
    return "Open Projections v. 1.0"

@app.route('/stats/<int:year>', methods=['PUT'])
def put_year_stats(year):
    build_logs.build_yearly_gamelogs(year)
    build_logs.combine_gamelogs()
    return "Built logs for " + str(year)

@app.route('/stats/<int:year>/<int:month>', methods=['PUT'])
def put_month_stats(year, month):
    build_logs.build_monthly_gamelogs(year, month)
    build_logs.combine_gamelogs()
    return "Built logs for " + str(year) + "-" + str(month)

@app.route('/stats/<int:year>/<int:month>/<int:day>', methods=['PUT'])
def put_day_stats(year, month, day):
    date_string = str(year) + "-" + str(month).zfill(2) + "-" + str(day).zfill(2)
    build_logs.build_daily_gamelogs(date_string)
    build_logs.combine_gamelogs()
    return "Built logs for " + date_string

@app.route('/projections/<string:date_string>', methods=['PUT'])
def put_projections(date_string):
    project.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/projections/', methods=['GET'])
def get_player_projections():
    if 'playerId' in request.args:
        player_id = int(request.args['playerId'])
    else:
        return "Error: No playerId provided. Please specify an (MLBAM) id."

    batting_name, bf = project.load_player_projections(player_id, True)

    # Did we find batting projections?
    if batting_name:
        df = bf
    else:
        pitching_name, pf = project.load_player_projections(player_id, False)
        df = pf

    return df.to_json(orient="records")

    
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)