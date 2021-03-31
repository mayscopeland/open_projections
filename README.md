# Open Projections
## Completely transparent, continually updated baseball forecasts

Unlike most projection systems, which use stats for past _seasons_, the Open Projections look at stats for each day. As a result, it can generate projections for any point in a season.

The basic formula weights all past stats by 0.9994^daysAgo for hitters, and 0.9990^daysAgo for pitchers. (These numbers come from Tom Tango, and are the basis for the Marcel projections' weights of 5/4/3 for hitters and 3/2/1 for pitchers.) Stats are regressed to the mean using the league average, weighted at 15% of PA for the player with the most PA in the sample.

Postseason games are included with equal weighting. Spring training and exhibition games count for 45% of a regular season game. (see [How much to weight spring training performances?](http://tangotiger.com/index.php/site/comments/how-much-to-weight-spring-training-performances))

Minor league stats are included with a rough adjustment for each level.

There's currently no projection for playing time. All players are projected for 650 PA.

### Want to help?

Contributions are welcome for code improvements.

Some low hanging fruit:
- Stat-specific decay rates
- Park adjustments
- Playing time projections
- Age adjustments (by stat)

Don't code? I'd also appreciate research-backed suggestions for improving the projections in any of these areas.
