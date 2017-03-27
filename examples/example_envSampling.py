import numpy as np
import ESSC
import copy

# Create buoy object, in this case for Station #46022
buoy46022 = ESSC.Buoy('46022')

# Read data from ndbc.noaa.gov
#buoy46022.fetchFromWeb()

# Load data from .txt file if avilable
buoy46022.loadFromText()

# Load data from .h5 file if available
#buoy46022.loadFromH5()

# Declare required parameters
depth = 391.4  # Depth at measurement point (m)
size_bin = 250.  # Enter chosen bin size

# Create EA object using above parameters
essc46022 = ESSC.EA(depth, size_bin, buoy46022)


Time_SS = 1.  # Sea state duration (hrs)
Time_R = np.array([100])  # Return periods (yrs) of interest
nb_steps = 1000.  # Enter discretization of the circle in the normal space

Hs_Return, T_Return = essc46022.getContours(Time_SS, Time_R, nb_steps)



# Sample Generation Example
num_contour_points = 20  # Number of points to be sampled for each
# contour interval.
contour_probs = 10 ** (-1 * np.array([1, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6]))
# Probabilities defining sampling contour bounds.
random_seed = 2  # Random seed for sample generation

# Get samples for a full sea state long term analysis
Hs_sampleFSS, T_sampleFSS, Weight_sampleFSS = essc46022.getSamples(num_contour_points,
                                                     contour_probs, random_seed)
# Get samples for a contour approach long term analysis
T_sampleCA = np.arange(5, 15, )
Hs_sampleCA = essc46022.getContourPoints(T_sampleCA)

# Modify contour by steepness curve if they intersect
SteepMax = 0.07  # Optional: enter estimate of breaking steepness
T_vals = np.arange(0.1, np.amax(buoy46022.T), 0.1)

SteepH = essc46022.steepness(SteepMax, T_vals)
SteepH_Return = essc46022.steepness(SteepMax, essc46022.T_ReturnContours)

Steep_correction = np.where(SteepH_Return < essc46022.Hs_ReturnContours)
Hs_Return_Steep = copy.deepcopy(essc46022.Hs_ReturnContours)
Hs_Return_Steep[Steep_correction] = SteepH_Return[Steep_correction]

essc46022.bootStrap(1000)

# Save data in h5 file
essc46022.saveData()

# Show a plot of the data
essc46022.plotData()