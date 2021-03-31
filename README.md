# Open Projections
## Completely transparent, continually updated baseball forecasts

Unlike most projection systems, which use stats for past _seasons_, the Open Projections look at stats for each _day_. As a result, it can generate projections for any point in a season.

### Methodology
The basic formula weights all past stats by 0.9994^daysAgo for hitters, and 0.9990^daysAgo for pitchers. (These numbers come from Tom Tango, and are similar to the Marcel projections' seasonal weights of 5/4/3 for hitters and 3/2/1 for pitchers.) Stats are regressed to the mean using the league average, weighted at 15% of the PA for the player with the most PA in the sample.

Postseason games are included with equal weighting to the regular season. Spring training and exhibition games count for 45%. (see [How much to weight spring training performances?](http://tangotiger.com/index.php/site/comments/how-much-to-weight-spring-training-performances))

Minor league stats are included with a rough adjustment for each level.

There's currently no projection for playing time. All players are projected for 650 PA.

### Usage
_(This could use a lot of polish, but it's what I have so far.)_

Before projecting, daily stats need to be pulled from the MLB Stats API using `build_logs.py`. Run `build_gamelogs(year)` for each of the six years before the intended projection date, and then `combine_player_logs()` to consolidate everything into a single file.

Projects are generated by calling `project_all(projectionDate)` in `project.py`, passing a string in the format "YYYY-MM-DD".

### Want to help?
Contributions are welcome for code improvements.

Some low-hanging fruit:
- Stat-specific decay rates and regression
- Park adjustments
- Age adjustments (by stat)
- Playing time projections

Don't code? I'd also appreciate research-backed suggestions for improving the projections in any of these areas.
