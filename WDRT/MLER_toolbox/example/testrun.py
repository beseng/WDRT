#!/usr/bin/python
import MLER

#RAOdir = '../RAO_data/'
#outputDir = 'TestData/'
RAOdir = 'RAO_data/'
outputDir = 'example/TestData/'

# Create the object
Test = MLER.focusedWave(H=9.0, T=15.1, numFreq=500)
Test.sim.setup()
print Test
print Test.waves
print Test.sim

# Setup the wave information
Test.waves.setup()
Test.waves.plotSpectrum()#show=True)

# Setup the RAO information
Test.readRAO(3,RAOdir+'RAO_heave_RM3float.dat')
Test.readRAO(5,RAOdir+'RAO_pitch_RM3float.dat')
Test.plotRAO(3)#,show=True)
Test.plotRAO(5,show=True)

# Now that everything is set up, generate the MLER wave for heave.
Test.MLERcoeffsGen(3,1.0) # generate the wave profile, 1 meter heave response desired

# At this point we can export the coefficients.  The coefficients will
# match a desired response height that was given as the second argument to
# MLERcoeffsGen.  But, if a specific height of the incoming wave is wanted,
# we can renormalize the wave amplitude now. (AP)
Test.MLERwaveAmpNormalize(Test.waves.H/2 * 1.9)     # the desired peak height (peak to MSL)

# Now export the heave coefficients.
Test.MLERexportCoeffs(outputDir+'Test_heave_MLER_heaveOpt_Coeffs.txt');

# Export the wave amplitude time series at x=x0 for heave.
Test.MLERexportWaveAmpTime(outputDir+'Test_heave_MLER_heaveOpt_heave_WaveAmpTime.txt',3)

# export the spectral info for WEC-Sim
#TODO: call Test.MLERexportWECSim('TestData/Test_heave_MLER_heaveOpt_WECSimInput.txt')


# TODO: animate, etc
# # make a movie of the sequence for heave
# MovieFramesHeave=Test.MLERanimate(3);
# # export movie of heave (don't add extension)
# Test.MLERexportMovie('Movie_Heave',MovieFramesHeave)
# 
# 
# # make a movie of the sequence for pitch
# MovieFramesPitch=Test.MLERanimate(5);
# # export movie of pitch (don't add extension)
# Test.MLERexportMovie('Movie_Pitch',MovieFramesPitch)
# 
# 
# # do some checks for heave vs. pitch optimized
# Test_heave.S = Test.S;
# 
# Test.MLERcoeffsGen(5,1);
# Test_pitch.S = Test.S;

