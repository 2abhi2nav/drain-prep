Rainfall-Based Urban Drainage Preparedness Recommender
Problem: Municipal authorities need to prioritize preparedness when rainfall patterns indicate an elevated risk of waterlogging.
Model: Rank preparedness actions or historical periods by rainfall intensity, accumulated rainfall, and historical extreme-rainfall frequency.
Analytics: Probability distributions, percentile analysis, confidence intervals, trend analysis, and a weighted decision matrix.
Data: IMD's daily gridded rainfall data, available from 1901 through 2024 on the archive page. 
Limitation: rainfall alone cannot establish whether a particular road will flood. Without historical flood labels, this is a preparedness-ranking model, not a validated flood predictor.

Gaps to fix

The “recommendation” is the weakest part. Ranking historical periods is descriptive. Make the output an actual recommendation: input a day’s rainfall (1-day and 3-day accumulated), convert it to a percentile or return period, assign a risk tier (e.g., Watch, Alert, Emergency), and output a recommended action set for each tier (pump deployment, drain desilting, shelter readiness). Your decision matrix then scores and prioritizes those actions.
Spatial resolution is coarse. IMD gridded data is 0.25° (about 25 km), so you can’t say anything about specific roads or wards. Pick the grid cell(s) covering Chennai and frame the model at city level.
Weights need justification. A weighted matrix with arbitrary weights is easy to criticize. Either derive them with AHP or run a sensitivity analysis showing the ranking holds when the weights change.
Validation workaround for the missing flood labels. You can’t validate against labels, but you can sanity-check: the model should rank known major flood episodes (Nov-Dec 2015, Nov 2021, Dec 2023) near the top of its risk tiers. That gives you a credible results section without formal flood data.
Add a stronger statistical core. For extreme rainfall, fit a Gumbel or GEV distribution to annual maxima and compute return periods (e.g., the 1-in-10-year rainfall) with confidence intervals. Use the Mann-Kendall test or a simple regression on annual maxima for the trend. Both are easy to defend in the report.

Practical note: The IMD files are in binary GRD format, so use Python’s imdlib library to read them. It saves a lot of time.
