# Copyright 2016 Sandia Corporation and the National Renewable Energy
# Laboratory
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import scipy.stats as stats
import scipy.optimize as optim
import scipy.interpolate as interp
import matplotlib.pyplot as plt
import h5py
from sklearn.decomposition import PCA as skPCA
import requests
import bs4
import urllib2
import re
from datetime import datetime, date
import os
import glob
import copy


class EA:

    def __init__():
        return
    def getContours():
        return
    def getSamples():
        return

    def saveData(self, fileName=None):
        """
        Saves all available data obtained via the EA module to
        a .h5 file

        Params
        ______
        fileName : string
            relevent path and filename where the .h5 file will be created and
            saved
        """
        if (fileName is None):
            fileName = 'NDBC' + str(self.buoy.buoyNum) + '.h5'
        else:
            _, file_extension = os.path.splitext(fileName)
            if not file_extension:
                fileName = fileName + '.h5'
        with h5py.File(fileName, 'w') as f:

            f.create_dataset('method', data=self.method)
            gp = f.create_group('parameters')
            self._saveParams(gp)

            if(self.buoy.Hs is not None):
                self.buoy._saveData(fileObj=f)

            if(self.Hs_ReturnContours is not None):
                grc = f.create_group('ReturnContours')
                f_T_Return = grc.create_dataset('T_Return', data=self.T_ReturnContours)
                f_T_Return.attrs['units'] = 's'
                f_T_Return.attrs['description'] = 'contour, energy period'
                f_Hs_Return = grc.create_dataset('Hs_Return', data=self.Hs_ReturnContours)
                f_Hs_Return.attrs['units'] = 'm'
                f_Hs_Return.attrs['description'] = 'contours, significant wave height'

            # Samples for full sea state long term analysis
            if(hasattr(self, 'Hs_SampleFSS') and self.Hs_SampleFSS is not None):
                gfss = f.create_group('Samples_FullSeaState')
                f_Hs_SampleFSS = gfss.create_dataset('Hs_SampleFSS', data=self.Hs_SampleFSS)
                f_Hs_SampleFSS.attrs['units'] = 'm'
                f_Hs_SampleFSS.attrs['description'] = 'full sea state significant wave height samples'
                f_T_SampleFSS = gfss.create_dataset('T_SampleFSS', data=self.T_SampleFSS)
                f_T_SampleFSS.attrs['units'] = 's'
                f_T_SampleFSS.attrs['description'] = 'full sea state energy period samples'
                f_Weight_SampleFSS = gfss.create_dataset('Weight_SampleFSS', data = self.Weight_SampleFSS)
                f_Weight_SampleFSS.attrs['description'] = 'full sea state relative weighting samples'

            # Samples for contour approach long term analysis
            if(hasattr(self, 'Hs_SampleCA') and self.Hs_SampleCA is not None):
                gca = f.create_group('Samples_ContourApproach')
                f_Hs_sampleCA = gca.create_dataset('Hs_SampleCA', data=self.Hs_SampleCA)
                f_Hs_sampleCA.attrs['units'] = 'm'
                f_Hs_sampleCA.attrs['description'] = 'contour approach significant wave height samples'
                f_T_sampleCA = gca.create_dataset('T_SampleCA', data=self.T_SampleCA)
                f_T_sampleCA.attrs['units'] = 's'
                f_T_sampleCA.attrs['description'] = 'contour approach energy period samples'

    def plotData(self):
        """
        Display a plot of the 100-year return contour, full sea state samples
        and contour samples
        """
        plt.figure()
        plt.plot(self.buoy.T, self.buoy.Hs, 'bo', alpha=0.1, label='NDBC data')
        plt.plot(self.T_ReturnContours, self.Hs_ReturnContours, 'k-', label='100 year contour')
        plt.plot(self.T_SampleFSS, self.Hs_SampleFSS, 'ro', label='full sea state samples')
        plt.plot(self.T_SampleCA, self.Hs_SampleCA, 'y^', label='contour approach samples')
        plt.legend(loc='lower right', fontsize='small')
        plt.grid(True)
        plt.xlabel('Energy period, $T_e$ [s]')
        plt.ylabel('Sig. wave height, $H_s$ [m]')
        plt.show()

    def getContourPoints(self, T_Sample):
        '''Get points along a specified environmental contour.

        Parameters
        ----------
            T_Sample : nparray
                points for sampling along return contour

        Returns
        -------
            Hs_SampleCA : nparray
                points sampled along return contour
        '''
        amin = np.argmin(self.T_ReturnContours)
        amax = np.argmax(self.T_ReturnContours)

        w1 = self.Hs_ReturnContours[amin:amax]
        w2 = np.concatenate((self.Hs_ReturnContours[amax:], self.Hs_ReturnContours[:amin]))
        if (np.max(w1) > np.max(w2)):
            x1 = self.T_ReturnContours[amin:amax]
            y = self.Hs_ReturnContours[amin:amax]
        else:
            x1 = np.concatenate((self.T_ReturnContours[amax:], self.T_ReturnContours[:amin]))
            y1 = np.concatenate((self.Hs_ReturnContours[amax:], self.Hs_ReturnContours[:amin]))

        ms = np.argsort(x1)
        x = x1[ms]
        y = y1[ms]

        si = interp.interp1d(x, y)

        Hs_SampleCA = si(T_Sample)

        self.T_SampleCA = T_Sample
        self.Hs_SampleCA = Hs_SampleCA
        return Hs_SampleCA

    def steepness(self, depth, SteepMax, T_vals):
        '''This function calculates a steepness curve to be plotted on an H vs. T
        diagram.  First, the function calculates the wavelength based on the
        depth and T. The T vector can be the input data vector, or will be
        created below to cover the span of possible T values.
        The function solves the dispersion relation for water waves
        using the Newton-Raphson method. All outputs are solved for exactly
        using: (w^2*h/g=kh*tanh(khG)
        Approximations that could be used in place of this code for deep
        and shallow water, as appropriate:
        deep water:h/lambda >= 1/2, tanh(kh)~1, lambda = (g.*T.^2)./(2*.pi)
        shallow water:h/lambda <= 1/20, tanh(kh)~kh, lambda = T.*(g.*h)^0.5

        Parameters
        ----------
        depth: float
            Depth at site
        SteepMax: float
            Wave breaking steepness estimate (e.g., 0.07).
        T_vals :np.array
            Array of T values [sec] at which to calculate the breaking height.

        Returns
        -------
        SteepH: np.array
            H values [m] that correspond to the T_mesh values creating the
            steepness curve.
        T_steep: np.array
            T values [sec] over which the steepness curve is defined.

        Example
        -------

        To find limit the steepness of waves on a contour by breaking::
            import numpy as np
            import WDRT.ESSC as ESSC

            # Pull spectral data from NDBC website
            buoy = ESSC.buoy(46022)
            buoy.fetchFromWeb()

            # Declare required parameters
            depth = 391.4  # Depth at measurement point (m)
            size_bin = 250.  # Enter chosen bin size

            # Create Environtmal Analysis object using above parameters
            ea = ESSC.ea(depth, size_bin, buoy)


            T_vals = np.arange(0.1, np.amax(buoy46022.T), 0.1)
            SteepMax = 0.07  # Optional: enter estimate of breaking steepness
            SteepH = ea.steepness(SteepMax,T_vals)
        '''

        # Calculate the wavelength at a given depth at each value of T
        lambdaT = []

        g = 9.81  # [m/s^2]
        omega = ((2 * np.pi) / T_vals)
        lambdaT = []

        for i in range(len(T_vals)):
            # Initialize kh using Eckert 1952 (mentioned in Holthuijsen pg. 124)
            kh = (omega[i]**2) * depth / \
                (g * (np.tanh((omega[i]**2) * depth / g)**0.5))
            # Find solution using the Newton-Raphson Method
            for j in range(1000):
                kh0 = kh
                f0 = (omega[i]**2) * depth / g - kh0 * np.tanh(kh0)
                df0 = -np.tanh(kh) - kh * (1 - np.tanh(kh)**2)
                kh = -f0 / df0 + kh0
                f = (omega[i]**2) * depth / g - kh * np.tanh(kh)
                if abs(f0 - f) < 10**(-6):
                    break

            lambdaT.append((2 * np.pi) / (kh / depth))
            del kh, kh0

        lambdaT = np.array(lambdaT, dtype=np.float)
        SteepH = lambdaT * SteepMax
        return SteepH

    def bootStrap(self, boot_size=1000, plotResults=True):
        '''Get 95% confidence bounds about a contour using the bootstrap
        method.

        Parameters
        ----------
            boot_size: int (optional)
                Number of bootstrap samples that will be used to calculate 95%
                confidence interval. Should be large enough to calculate stable
                statistics. If left blank will be set to 1000.
            plotResults: boolean (optional)
                Option for showing plot of bootstrap confidence bounds. If left
                blank will be set to True and plot will be shown.

        Returns
        -------
            contourmean_Hs : nparray
                Hs values for mean contour calculated as the average over all
                bootstrap contours.
            contourmean_T : nparray
                T values for mean contour calculated as the average over all
                bootstrap contours.
        '''
        n = len(self.buoy.Hs)
        Hs_Return_Boot = np.zeros([self.nb_steps,boot_size])
        T_Return_Boot = np.zeros([self.nb_steps,boot_size])
        buoycopy = copy.deepcopy(self.buoy);

        for i in range(boot_size):
            boot_inds = np.random.randint(0, high=n, size=n)
            buoycopy.Hs = copy.deepcopy(self.buoy.Hs[boot_inds])
            buoycopy.T = copy.deepcopy(self.buoy.T[boot_inds])
            if self.method == "PCA":
                essccopy = PCA(buoycopy, self.size_bin)
            elif self.method == "GaussianCopula":
                essccopy = GaussianCopula(buoycopy, self.n_size, self.bin_1_limit, self.bin_step)
            elif self.method == "Rosenblatt":
                essccopy = Rosenblatt(buoycopy, self.n_size, self.bin_1_limit, self.bin_step)
            elif self.method == "ClaytonCopula":
                essccopy = ClaytonCopula(buoycopy, self.n_size, self.bin_1_limit, self.bin_step)
            elif self.method == "GumbelCopula":
                essccopy = GumbelCopula(buoycopy, self.n_size, self.bin_1_limit, self.bin_step, self.Ndata)
            Hs_Return_Boot[:,i],T_Return_Boot[:,i] = essccopy.getContours(self.time_ss, self.time_r, self.nb_steps)

        contour97_5_Hs = np.percentile(Hs_Return_Boot,97.5,axis=1)
        contour2_5_Hs = np.percentile(Hs_Return_Boot,2.5,axis=1)
        contourmean_Hs = np.mean(Hs_Return_Boot, axis=1)

        contour97_5_T = np.percentile(T_Return_Boot,97.5,axis=1)
        contour2_5_T = np.percentile(T_Return_Boot,2.5,axis=1)
        contourmean_T = np.mean(T_Return_Boot, axis=1)

        self.contourMean_Hs = contourmean_Hs
        self.contourMean_T = contourmean_T

        def plotResults():
            plt.figure()
            plt.plot(self.buoy.T, self.buoy.Hs, 'bo', alpha=0.1, label='NDBC data')
            plt.plot(self.T_ReturnContours, self.Hs_ReturnContours, 'k-', label='100 year contour')
            plt.plot(contour97_5_T, contour97_5_Hs, 'r--', label='95% bootstrap confidence interval')
            plt.plot(contour2_5_T, contour2_5_Hs, 'r--')
            plt.plot(contourmean_T, contourmean_Hs, 'r-', label='Mean bootstrap contour')
            plt.legend(loc='lower right', fontsize='small')
            plt.grid(True)
            plt.xlabel('Energy period, $T_e$ [s]')
            plt.ylabel('Sig. wave height, $H_s$ [m]')
            plt.show()
        if plotResults:
            plotResults()

        return contourmean_Hs, contourmean_T

    def __getCopulaParams(self,n_size,bin_1_limit,bin_step):
        sorted_idx = sorted(range(len(self.buoy.Hs)),key=lambda x:self.buoy.Hs[x])
        Hs = self.buoy.Hs[sorted_idx]
        T = self.buoy.T[sorted_idx]

        # Estimate parameters for Weibull distribution for component 1 (Hs) using MLE
        # Estimate parameters for Lognormal distribution for component 2 (T) using MLE
        para_dist_1=stats.exponweib.fit(Hs,floc=0,fa=1)
        para_dist_2=stats.norm.fit(np.log(T))

        # Binning
        ind = np.array([])
        ind = np.append(ind,sum(Hs_val <= bin_1_limit for Hs_val in Hs))
        for i in range(1,200):
            bin_i_limit = bin_1_limit+bin_step*(i)
            ind = np.append(ind,sum(Hs_val <= bin_i_limit for Hs_val in Hs))
            if (ind[i-0]-ind[i-1]) < n_size:
                break

        # Parameters for conditional distribution of T|Hs for each bin
        num=len(ind) # num+1: number of bins
        para_dist_cond = []
        hss = []

        para_dist_cond.append(stats.norm.fit(np.log(T[range(0,int(ind[0]))])))  # parameters for first bin
        hss.append(np.mean(Hs[range(0,int(ind[0])-1)])) # mean of Hs (component 1 for first bin)
        para_dist_cond.append(stats.norm.fit(np.log(T[range(0,int(ind[1]))]))) # parameters for second bin
        hss.append(np.mean(Hs[range(0,int(ind[1])-1)])) # mean of Hs (component 1 for second bin)

        for i in range(2,num):
            para_dist_cond.append(stats.norm.fit(np.log(T[range(int(ind[i-2]),int(ind[i]))])));
            hss.append(np.mean(Hs[range(int(ind[i-2]),int(ind[i]))]))

        # Estimate coefficient using least square solution (mean: third order, sigma: 2nd order)
        para_dist_cond.append(stats.norm.fit(np.log(T[range(int(ind[num-2]),int(len(Hs)))])));  # parameters for last bin
        hss.append(np.mean(Hs[range(int(ind[num-2]),int(len(Hs)))])) # mean of Hs (component 1 for last bin)

        para_dist_cond = np.array(para_dist_cond)
        hss = np.array(hss)

        phi_mean = np.column_stack((np.ones(num+1),hss[:],hss[:]**2,hss[:]**3))
        phi_std = np.column_stack((np.ones(num+1),hss[:],hss[:]**2))

        # Estimate coefficients of mean of Ln(T|Hs)(vector 4x1) (cubic in Hs)
        mean_cond = np.linalg.lstsq(phi_mean,para_dist_cond[:,0])[0]
        # Estimate coefficients of standard deviation of Ln(T|Hs) (vector 3x1) (quadratic in Hs)
        std_cond = np.linalg.lstsq(phi_std,para_dist_cond[:,1])[0]

        return para_dist_1, para_dist_2, mean_cond, std_cond


class PCA(EA):

    def __init__(self, buoy, size_bin=250.):
        '''
        Parameters
        ___________
            size_bin : float
                chosen bin size
            buoy : NDBCData
                ESSC.Buoy Object
        '''
        self.method = "Principle component analysis"
        self.buoy = buoy
        self.size_bin = size_bin

        self.Hs_ReturnContours = None
        self.Hs_SampleCA = None
        self.Hs_SampleFSS = None

        self.T_ReturnContours = None
        self.T_SampleCA = None
        self.T_SampleFSS = None

        self.Weight_points = None

        self.coeff, self.shift, self.comp1_params, self.sigma_param, self.mu_param = self.__generateParams(size_bin)

    def __generateParams(self, size_bin=250.0):
        pca = skPCA(n_components=2)
        pca.fit(np.array((self.buoy.Hs - self.buoy.Hs.mean(axis=0), self.buoy.T - self.buoy.T.mean(axis=0))).T)
        coeff = abs(pca.components_)  # Apply correct/expected sign convention
        coeff[1, 1] = -1.0 * coeff[1, 1]  # Apply correct/expected sign convention

        Comp1_Comp2 = np.dot (np.array((self.buoy.Hs, self.buoy.T)).T, coeff)

        shift = abs(min(Comp1_Comp2[:, 1])) + 0.1  # Calculate shift


        shift = abs(min(Comp1_Comp2[:, 1])) + 0.1  # Calculate shift
        # Apply shift to Component 2 to make all values positive
        Comp1_Comp2[:, 1] = Comp1_Comp2[:, 1] + shift

        Comp1_Comp2_sort = Comp1_Comp2[Comp1_Comp2[:, 0].argsort(), :]

        # Fitting distribution of component 1
        comp1_params = stats.invgauss.fit(Comp1_Comp2_sort[:, 0], floc=0)

        n_data = len(self.buoy.Hs)  # Number of observations

        edges = np.hstack((np.arange(0, size_bin * np.ceil(n_data / size_bin),
                         size_bin), n_data + 1))
        ranks = np.arange(n_data)
        hist_count, _ = np.histogram(ranks, bins=edges)
        bin_inds = np.digitize(ranks, bins=edges) - 1
        Comp2_bins_params = np.zeros((2, int(max(bin_inds) + 1)))
        Comp1_mean = np.array([])

        for bin_loop in range(np.max(bin_inds) + 1):
            mask_bins = bin_inds == bin_loop  # Find location of bin values
            Comp2_bin = np.sort(Comp1_Comp2_sort[mask_bins, 1])
            Comp1_mean = np.append(Comp1_mean,
                                   np.mean(Comp1_Comp2_sort[mask_bins, 0]))
            # Calcualte normal distribution parameters for C2 in each bin
            Comp2_bins_params[:, bin_loop] = np.array(stats.norm.fit(Comp2_bin))

        mu_param, pcov = optim.curve_fit(self.__mu_fcn,
                                                 Comp1_mean.T, Comp2_bins_params[0, :])

        sigma_param = self.__sigma_fits(Comp1_mean, Comp2_bins_params[1, :])

        return coeff, shift, comp1_params, sigma_param, mu_param

    def _saveParams(self, groupObj):
        groupObj.create_dataset('nb_steps', data=self.nb_steps)
        groupObj.create_dataset('time_r', data=self.time_r)
        groupObj.create_dataset('time_ss', data=self.time_ss)
        groupObj.create_dataset('coeff', data=self.coeff)
        groupObj.create_dataset('shift', data=self.shift)
        groupObj.create_dataset('comp1_params', data=self.comp1_params)
        groupObj.create_dataset('sigma_param', data=self.sigma_param)
        groupObj.create_dataset('mu_param', data=self.mu_param)

    def getContours(self, time_ss, time_r, nb_steps=1000):
        '''WDRT Extreme Sea State PCA Contour function
        This function calculates environmental contours of extreme sea states using
        principal component analysis and the inverse first-order reliability
        method.

        Parameters
        ___________
        time_ss : float
            Sea state duration (hours) of measurements in input.
        time_r : np.array
            Desired return period (years) for calculation of environmental
            contour, can be a scalar or a vector.
        nb_steps : float
            Discretization of the circle in the normal space used for
            inverse FORM calculation.

        Returns
        -------
        Hs_Return : np.array
            Calculated Hs values along the contour boundary following
            return to original input orientation.
        T_Return : np.array
           Calculated T values along the contour boundary following
           return to original input orientation.
        nb_steps : float
            Discretization of the circle in the normal space

        Example
        -------
        To obtain the contours for a NDBC buoy::
            import numpy as np
            import WDRT.ESSC as ESSC
            # Pull spectral data from NDBC website
            buoy = ESSC.buoy('46022')
            buoy.fetchFromWeb()

            # Declare required parameters
            depth = 391.4  # Depth at measurement point (m)
            size_bin = 250.  # Enter chosen bin size

            # Create Environtmal Analysis object using above parameters
            pca46022 = ESSC.PCA(depth, buoy, size_bin)

            # used for inverse FORM calculation
            Time_SS = 1.  # Sea state duration (hrs)
            Time_r = np.array([100])  # Return periods (yrs) of interest

            nb_steps = 1000.  # Enter discretization of the circle in the normal space

            # Contour generation example
            Hs_Return, T_Return = pca46022.getContours(Time_SS, Time_r, nb_steps)
        '''

        self.time_ss = time_ss
        self.time_r = time_r
        self.nb_steps = nb_steps

        # IFORM
        # Failure probability for the desired return period (time_R) given the
        # duration of the measurements (time_ss)
        p_f = 1 / (365 * (24 / time_ss) * time_r)
        beta = stats.norm.ppf((1 - p_f), loc=0, scale=1)  # Reliability
        theta = np.linspace(0, 2 * np.pi, num = nb_steps)
        # Vary U1, U2 along circle sqrt(U1^2+U2^2)=beta
        U1 = beta * np.cos(theta)
        U2 = beta * np.sin(theta)
        # Calculate C1 values along the contour
        Comp1_R = stats.invgauss.ppf(stats.norm.cdf(U1, loc=0, scale=1),
                                     mu= self.comp1_params[0], loc=0,
                                     scale= self.comp1_params[2])
        # Calculate mu values at each point on the circle
        mu_R = self.__mu_fcn(Comp1_R, self.mu_param[0], self.mu_param[1])
        # Calculate sigma values at each point on the circle
        sigma_R = self.__sigma_fcn(self.sigma_param, Comp1_R)
        # Use calculated mu and sigma values to calculate C2 along the contour
        Comp2_R = stats.norm.ppf(stats.norm.cdf(U2, loc=0, scale=1),
                                 loc=mu_R, scale=sigma_R)

        # Calculate Hs and T along the contour
        Hs_Return, T_Return = self.__princomp_inv(Comp1_R, Comp2_R, self.coeff, self.shift)
        Hs_Return = np.maximum(0, Hs_Return)  # Remove negative values
        self.Hs_ReturnContours = Hs_Return
        self.T_ReturnContours = T_Return
        return Hs_Return, T_Return

    def getSamples(self, num_contour_points, contour_returns, random_seed=None):
        '''WDRT Extreme Sea State Contour Sampling function
        This function calculates samples of Hs and T using the EA function to
        sample between contours of user-defined return periods.

        Parameters
        ----------
        num_contour_points : int
            Number of sample points to be calculated per contour interval.
        contour_returns: np.array
            Vector of return periods that define the contour intervals in
            which samples will be taken. Values must be greater than zero and
            must be in increasing order.
        random_seed: int (optional)
            Random seed for sample generation, required for sample
            repeatability. If left blank, a seed will automatically be
            generated.

        Returns
        -------
        Hs_Samples: np.array
            Vector of Hs values for each sample point.
        Te_Samples: np.array
            Vector of Te values for each sample point.
        Weight_points: np.array
            Vector of probabilistic weights for each sampling point
            to be used in risk calculations.

        Example
        -------
        To get weighted samples from a set of contours::

            import numpy as np
            import WDRT.ESSC as ESSC
            # Load data from existing text files
            buoy = ESSC.Buoy(46022)
            buoy.loadFromText()

            depth = float(675) # Depth at measurement point (m)
            size_bin = float(250) # Enter chosen bin size
            nb_steps = float(1000) # Enter discretization of the circle in the

            # normal space. Used for inverse FORM calculation.
            Time_SS = float(1) # Sea state duration (hrs)
            Time_r = np.array([100]) # Return periods (yrs) of interest
            num_contour_points = 10 # Number of points to be sampled for each

            # contour interval.
            contour_returns = np.array([0.001,0.01,0.05,0.1,0.5,1,5,10,50,100])

            # Probabilities defining sampling contour bounds.
            random_seed = 2 # Random seed for sample generation
            Hs_Sample,T_Sample,Weight_points = EA.getSamples(nb_steps,
            Time_SS,Time_r)
        '''

        # Calculate line where Hs = 0 to avoid sampling Hs in negative space
        Te_zeroline = np.linspace(2.5, 30, 1000)
        Te_zeroline = np.transpose(Te_zeroline)
        Hs_zeroline = np.zeros(len(Te_zeroline))

        # Transform zero line into principal component space
        Comp_zeroline = np.dot(np.transpose(np.vstack([Hs_zeroline, Te_zeroline])),
                               self.coeff)
        Comp_zeroline[:, 1] = Comp_zeroline[:, 1] + self.shift

        # Find quantiles along zero line
        C1_zeroline_prob = stats.invgauss.cdf(Comp_zeroline[:, 0],
                                              mu = self.comp1_params[0], loc=0,
                                              scale = self.comp1_params[2])
        mu_zeroline = self.__mu_fcn(Comp_zeroline[:, 0], self.mu_param[0], self.mu_param[1])
        sigma_zeroline = self.__sigma_fcn(self.sigma_param, Comp_zeroline[:, 0])
        C2_zeroline_prob = stats.norm.cdf(Comp_zeroline[:, 1],
                                          loc=mu_zeroline, scale=sigma_zeroline)
        C1_normzeroline = stats.norm.ppf(C1_zeroline_prob, 0, 1)
        C2_normzeroline = stats.norm.ppf(C2_zeroline_prob, 0, 1)

        contour_probs = 1 / (365 * (24 / self.time_ss) * contour_returns)
        # Reliability contour generation
        beta_lines = stats.norm.ppf(
            (1 - contour_probs), 0, 1)  # Calculate reliability
        beta_lines = np.hstack((0, beta_lines))  # Add zero as lower bound to first
        # contour
        theta_lines = np.linspace(0, 2 * np.pi, 1000)  # Discretize the circle

        contour_probs = np.hstack((1, contour_probs))  # Add probablity of 1 to the
        # reliability set, corresponding to probability of the center point of the
        # normal space

        # Vary U1,U2 along circle sqrt(U1^2+U2^2) = beta
        U1_lines = np.dot(np.cos(theta_lines[:, None]), beta_lines[None, :])
        U2_lines = np.dot(np.sin(theta_lines[:, None]), beta_lines[None, :])

        # Removing values on the H_s = 0 line that are far from the circles in the
        # normal space that will be evaluated to speed up calculations
        minval = np.amin(U1_lines) - 0.5
        mask = C1_normzeroline > minval
        C1_normzeroline = C1_normzeroline[mask]
        C2_normzeroline = C2_normzeroline[mask]

        # Transform to polar coordinates
        Theta_zeroline = np.arctan2(C2_normzeroline, C1_normzeroline)
        Rho_zeroline = np.sqrt(C1_normzeroline**2 + C2_normzeroline**2)
        Theta_zeroline[Theta_zeroline < 0] = Theta_zeroline[
            Theta_zeroline < 0] + 2 * np.pi


        Sample_alpha, Sample_beta, Weight_points = self.__generateData(beta_lines,
            Rho_zeroline, Theta_zeroline, num_contour_points,contour_probs,random_seed)

        Hs_Sample, T_Sample = self.__transformSamples(Sample_alpha, Sample_beta)

        self.Hs_SampleFSS = Hs_Sample
        self.T_SampleFSS = T_Sample
        self.Weight_SampleFSS = Weight_points

        return Hs_Sample, T_Sample, Weight_points

    def __generateData(self, beta_lines, Rho_zeroline, Theta_zeroline, num_contour_points, contour_probs, random_seed):
        """
        Calculates radius, angle, and weight for each sample point
        """
        np.random.seed(random_seed)

        num_samples = (len(beta_lines) - 1) * num_contour_points
        Alpha_bounds = np.zeros((len(beta_lines) - 1, 2))
        Angular_dist = np.zeros(len(beta_lines) - 1)
        Angular_ratio = np.zeros(len(beta_lines) - 1)
        Alpha = np.zeros((len(beta_lines) - 1, num_contour_points + 1))
        Weight = np.zeros(len(beta_lines) - 1)
        Sample_beta = np.zeros(num_samples)
        Sample_alpha = np.zeros(num_samples)
        Weight_points = np.zeros(num_samples)

        for i in range(len(beta_lines) - 1):  # Loop over contour intervals
            # Check if any of the radii for the
            r = Rho_zeroline - beta_lines[i + 1]
            # Hs=0, line are smaller than the radii of the contour, meaning
            # that these lines intersect
            if any(r < 0):
                left = np.amin(np.where(r < -0.01))
                right = np.amax(np.where(r < -0.01))
                Alpha_bounds[i, :] = (Theta_zeroline[left], Theta_zeroline[right] -
                                      2 * np.pi)  # Save sampling bounds
            else:
                Alpha_bounds[i, :] = np.array((0, 2 * np.pi))
                            # Find the angular distance that will be covered by sampling the disc
            Angular_dist[i] = sum(abs(Alpha_bounds[i]))
            # Calculate ratio of area covered for each contour
            Angular_ratio[i] = Angular_dist[i] / (2 * np.pi)
            # Discretize the remaining portion of the disc into 10 equally spaced
            # areas to be sampled
            Alpha[i, :] = np.arange(min(Alpha_bounds[i]),
                                    max(Alpha_bounds[i]) + 0.1, Angular_dist[i] / num_contour_points)
            # Calculate the weight of each point sampled per contour
            Weight[i] = ((contour_probs[i] - contour_probs[i + 1]) *
                         Angular_ratio[i] / num_contour_points)
            for j in range(num_contour_points):
                # Generate sample radius by adding a randomly sampled distance to
                # the 'disc' lower bound
                Sample_beta[(i) * num_contour_points + j] = (beta_lines[i] +
                                                             np.random.random_sample() * (beta_lines[i + 1] - beta_lines[i]))
                # Generate sample angle by adding a randomly sampled distance to
                # the lower bound of the angle defining a discrete portion of the
                # 'disc'
                Sample_alpha[(i) * num_contour_points + j] = (Alpha[i, j] +
                                                              np.random.random_sample() * (Alpha[i, j + 1] - Alpha[i, j]))
                # Save the weight for each sample point
                Weight_points[(i) * num_contour_points + j] = Weight[i]

        return Sample_alpha, Sample_beta, Weight_points

    def __transformSamples(self, Sample_alpha, Sample_beta):
        Sample_U1 = Sample_beta * np.cos(Sample_alpha)
        Sample_U2 = Sample_beta * np.sin(Sample_alpha)

        # Sample transformation to principal component space
        Comp1_sample = stats.invgauss.ppf(stats.norm.cdf(Sample_U1, loc=0, scale=1),
                                          mu=self.comp1_params[0], loc=0,
                                          scale=self.comp1_params[2])
        mu_sample = self.__mu_fcn(Comp1_sample, self.mu_param[0], self.mu_param[1])
        # Calculate sigma values at each point on the circle
        sigma_sample = self.__sigma_fcn(self.sigma_param, Comp1_sample)
        # Use calculated mu and sigma values to calculate C2 along the contour
        Comp2_sample = stats.norm.ppf(stats.norm.cdf(Sample_U2, loc=0, scale=1),
                                      loc=mu_sample, scale=sigma_sample)
        # Sample transformation into Hs-T space
        Hs_Sample, T_Sample = self.__princomp_inv(
            Comp1_sample, Comp2_sample, self.coeff, self.shift)

        return Hs_Sample, T_Sample


    def __mu_fcn(self, x, mu_p_1, mu_p_2):
        ''' Linear fitting function for the mean(mu) of Component 2 normal
        distribution as a function of the Component 1 mean for each bin.
        Used in the EA and getSamples functions.
        Parameters
        ----------
        mu_p: np.array
               Array of mu fitting function parameters.
        x: np.array
           Array of values (Component 1 mean for each bin) at which to evaluate
           the mu fitting function.
        Returns
        -------
        mu_fit: np.array
                Array of fitted mu values.
        '''
        mu_fit = mu_p_1 * x + mu_p_2
        return mu_fit


    def __sigma_fcn(self,sig_p, x):
        '''Quadratic fitting formula for the standard deviation(sigma) of Component
        2 normal distribution as a function of the Component 1 mean for each bin.
        Used in the EA and getSamples functions.
        Parameters
        ----------
        sig_p: np.array
               Array of sigma fitting function parameters.
        x: np.array
           Array of values (Component 1 mean for each bin) at which to evaluate
           the sigma fitting function.
        Returns
        -------
        sigma_fit: np.array
                   Array of fitted sigma values.
        '''
        sigma_fit = sig_p[0] * x**2 + sig_p[1] * x + sig_p[2]
        return sigma_fit


    def __princomp_inv(self, princip_data1, princip_data2, coeff, shift):
        '''Takes the inverse of the principal component rotation given data,
        coefficients, and shift. Used in the EA and getSamples functions.
        Parameters
        ----------
        princip_data1: np.array
                       Array of Component 1 values.
        princip_data2: np.array
                       Array of Component 2 values.
        coeff: np.array
               Array of principal component coefficients.
        shift: float
               Shift applied to Component 2 to make all values positive.
        Returns
        -------
        original1: np.array
                   Hs values following rotation from principal component space.
        original2: np.array
                   T values following rotation from principal component space.
        '''
        original1 = np.zeros(len(princip_data1))
        original2 = np.zeros(len(princip_data1))
        for i in range(len(princip_data2)):
            original1[i] = (((coeff[0, 1] * (princip_data2[i] - shift)) +
                             (coeff[0, 0] * princip_data1[i])) / (coeff[0, 1]**2 +
                                                                  coeff[0, 0]**2))
            original2[i] = (((coeff[0, 1] * princip_data1[i]) -
                             (coeff[0, 0] * (princip_data2[i] -
                                             shift))) / (coeff[0, 1]**2 + coeff[0, 0]**2))
        return original1, original2

    def __betafcn(self, sig_p, rho):
        '''Penalty calculation for sigma parameter fitting function to impose
        positive value constraint.
        Parameters
        ----------
        sig_p: np.array
               Array of sigma fitting function parameters.
        rho: float
             Penalty function variable that drives the solution towards
             required constraint.
        Returns
        -------
        Beta1: float
               Penalty function variable that applies the constraint requiring
               the y-intercept of the sigma fitting function to be greater than
               or equal to 0.
        Beta2: float
               Penalty function variable that applies the constraint requiring
               the minimum of the sigma fitting function to be greater than or
               equal to 0.
        '''
        if -sig_p[2] <= 0:
            Beta1 = 0.0
        else:
            Beta1 = rho
        if -sig_p[2] + (sig_p[1]**2) / (4 * sig_p[0]) <= 0:
            Beta2 = 0.0
        else:
            Beta2 = rho
        return Beta1, Beta2

    # Sigma function sigma_fcn defined outside of EA function

    def __objfun(self, sig_p, x, y_actual):
        '''Sum of least square error objective function used in sigma
        minimization.
        Parameters
        ----------
        sig_p: np.array
               Array of sigma fitting function parameters.
        x: np.array
           Array of values (Component 1 mean for each bin) at which to evaluate
           the sigma fitting function.
        y_actual: np.array
                  Array of actual sigma values for each bin to use in least
                  square error calculation with fitted values.
        Returns
        -------
        obj_fun_result: float
                        Sum of least square error objective function for fitted
                        and actual values.
        '''
        obj_fun_result = np.sum((self.__sigma_fcn(sig_p, x) - y_actual)**2)
        return obj_fun_result  # Sum of least square error

    def __objfun_penalty(self, sig_p, x, y_actual, Beta1, Beta2):
        '''Penalty function used for sigma function constrained optimization.
        Parameters
        ----------
        sig_p: np.array
               Array of sigma fitting function parameters.
        x: np.array
           Array of values (Component 1 mean for each bin) at which to evaluate
           the sigma fitting function.
        y_actual: np.array
                  Array of actual sigma values for each bin to use in least
                  square error calculation with fitted values.
        Beta1: float
               Penalty function variable that applies the constraint requiring
               the y-intercept of the sigma fitting function to be greater than
               or equal to 0.
        Beta2: float
               Penalty function variable that applies the constraint requiring
               the minimum of the sigma fitting function to be greater than or
               equal to 0.
        Returns
        -------
        penalty_fcn: float
                     Objective function result with constraint penalties
                     applied for out of bound solutions.
        '''
        penalty_fcn = (self.__objfun(sig_p, x, y_actual) + Beta1 * (-sig_p[2])**2 +
                       Beta2 * (-sig_p[2] + (sig_p[1]**2) / (4 * sig_p[0]))**2)
        return penalty_fcn

    def __sigma_fits(self, Comp1_mean, sigma_vals):
        '''Sigma parameter fitting function using penalty optimization.
        Parameters
        ----------
        Comp1_mean: np.array
                    Mean value of Component 1 for each bin of Component 2.
        sigma_vals: np.array
                    Value of Component 2 sigma for each bin derived from normal
                    distribution fit.
        Returns
        -------
        sig_final: np.array
                   Final sigma parameter values after constrained optimization.
        '''
        sig_0 = np.array((0.1, 0.1, 0.1))  # Set initial guess
        rho = 1.0  # Set initial penalty value
        # Set tolerance, very small values (i.e.,smaller than 10^-5) may cause
        # instabilities
        epsilon = 10**-5
        # Set inital beta values using beta function
        Beta1, Beta2 = self.__betafcn(sig_0, rho)
        # Initial search for minimum value using initial guess
        sig_1 = optim.fmin(func=self.__objfun_penalty, x0=sig_0,
                           args=(Comp1_mean, sigma_vals, Beta1, Beta2), disp=False)
        # While either the difference between iterations or the difference in
        # objective function evaluation is greater than the tolerance, continue
        # iterating
        while (np.amin(abs(sig_1 - sig_0)) > epsilon and
               abs(self.__objfun(sig_1, Comp1_mean, sigma_vals) -
                   self.__objfun(sig_0, Comp1_mean, sigma_vals)) > epsilon):
            sig_0 = sig_1
            # Calculate penalties for this iteration
            Beta1, Beta2 = self.__betafcn(sig_0, rho)
            # Find a new minimum
            sig_1 = optim.fmin(func=self.__objfun_penalty, x0=sig_0,
                               args=(Comp1_mean, sigma_vals, Beta1, Beta2), disp=False)
            rho = 10 * rho  # Increase penalization
        sig_final = sig_1
        return sig_final


class GaussianCopula(EA):

    def __init__(self, buoy, n_size=40., bin_1_limit=1., bin_step=0.25):
        '''
        Parameters
        ___________
            depth : int
                Depth at measurement point (m)
            buoy : NDBCData
                ESSC.Buoy Object
            n_size: float
                minimum bin size used for Copula contour methods
            bin_1_limit: float
                maximum value of Hs for the first bin
            bin_step: float
                overlap interval for each bin
        '''
        self.method = "Gaussian Copula"
        self.buoy = buoy
        self.n_size = n_size
        self.bin_1_limit = bin_1_limit
        self.bin_step = bin_step

        self.Hs_ReturnContours = None
#        self.Hs_SampleCA = None
#        self.Hs_SampleFSS = None

        self.T_ReturnContours = None
#        self.T_SampleCA = None
#        self.T_SampleFSS = None

#        self.Weight_points = None

#        self.coeff, self.shift, self.comp1_params, self.sigma_param, self.mu_param = self.__generateParams(size_bin)
        self.para_dist_1,self.para_dist_2,self.mean_cond,self.std_cond = self._EA__getCopulaParams(n_size,bin_1_limit,bin_step)

    def getContours(self, time_ss, time_r, nb_steps = 1000):
        '''WDRT Extreme Sea State Gaussian Copula Contour function
        This function calculates environmental contours of extreme sea states using
        a Gaussian copula and the inverse first-order reliability
        method.

        Parameters
        ___________
        time_ss : float
            Sea state duration (hours) of measurements in input.
        time_r : np.array
            Desired return period (years) for calculation of environmental
            contour, can be a scalar or a vector.
        nb_steps : float
            Discretization of the circle in the normal space used for
            inverse FORM calculation.

        Returns
        -------
        Hs_Return : np.array
            Calculated Hs values along the contour boundary following
            return to original input orientation.
        T_Return : np.array
           Calculated T values along the contour boundary following
           return to original input orientation.
        nb_steps : float
            Discretization of the circle in the normal space

        Example
        -------
        To obtain the contours for a NDBC buoy::
            import numpy as np
            import WDRT.ESSC as ESSC
            # Pull spectral data from NDBC website
            buoy = ESSC.buoy('46022')
            buoy.fetchFromWeb()

            # Declare required parameters
            depth = 391.4  # Depth at measurement point (m)

            # Create Environtmal Analysis object using above parameters
            Gauss46022 = ESSC.GaussianCopula(depth, buoy)

            # used for inverse FORM calculation
            Time_SS = 1.  # Sea state duration (hrs)
            Time_r = np.array([100])  # Return periods (yrs) of interest

            nb_steps = 1000.  # Enter discretization of the circle in the normal space

            # Contour generation example
            Hs_Return, T_Return = Gauss46022.getContours(Time_SS, Time_r, nb_steps)
        '''
        self.time_ss = time_ss
        self.time_r = time_r
        self.nb_steps = nb_steps

        p_f = 1 / (365 * (24 / time_ss) * time_r)
        beta = stats.norm.ppf((1 - p_f), loc=0, scale=1)  # Reliability
        theta = np.linspace(0, 2 * np.pi, num = nb_steps)
        # Vary U1, U2 along circle sqrt(U1^2+U2^2)=beta
        U1 = beta * np.cos(theta)
        U2 = beta * np.sin(theta)

        comp_1 = stats.exponweib.ppf(stats.norm.cdf(U1),a=self.para_dist_1[0],c=self.para_dist_1[1],loc=self.para_dist_1[2],scale=self.para_dist_1[3])

        tau = stats.kendalltau(self.buoy.T,self.buoy.Hs)[0] # Calculate Kendall's tau
        rho_gau=np.sin(tau*np.pi/2.)

        z2_Gau=stats.norm.cdf(U2*np.sqrt(1.-rho_gau**2.)+rho_gau*U1);
        comp_2_Gaussian = stats.lognorm.ppf(z2_Gau,s=self.para_dist_2[1],loc=0,scale=np.exp(self.para_dist_2[0])) #lognormalinverse

        Hs_Return = comp_1
        T_Return = comp_2_Gaussian

        self.Hs_ReturnContours = Hs_Return
        self.T_ReturnContours = T_Return
        return Hs_Return, T_Return

    def getSamples(self):
        raise NotImplementedError

    def _saveParams(self, groupObj):
        groupObj.create_dataset('n_size', data=self.n_size)
        groupObj.create_dataset('bin_1_limit', data=self.bin_1_limit)
        groupObj.create_dataset('bin_step', data=self.bin_step)
        groupObj.create_dataset('para_dist_1', data=self.para_dist_1)
        groupObj.create_dataset('para_dist_2', data=self.para_dist_2)
        groupObj.create_dataset('mean_cond', data=self.mean_cond)
        groupObj.create_dataset('std_cond', data=self.std_cond)


class Rosenblatt(EA):
    def __init__(self, buoy, n_size=40., bin_1_limit=1., bin_step=0.25):
        '''
        Parameters
        ___________
            depth : int
                Depth at measurement point (m)
            buoy : NDBCData
                ESSC.Buoy Object
            n_size: float
                minimum bin size used for Copula contour methods
            bin_1_limit: float
                maximum value of Hs for the first bin
            bin_step: float
                overlap interval for each bin
        '''
        self.method = "Rosenblatt"
        self.buoy = buoy
        self.n_size = n_size
        self.bin_1_limit = bin_1_limit
        self.bin_step = bin_step

        self.Hs_ReturnContours = None
#        self.Hs_SampleCA = None
#        self.Hs_SampleFSS = None

        self.T_ReturnContours = None
#        self.T_SampleCA = None
#        self.T_SampleFSS = None

#        self.Weight_points = None

#        self.coeff, self.shift, self.comp1_params, self.sigma_param, self.mu_param = self.__generateParams(size_bin)
        self.para_dist_1,self.para_dist_2,self.mean_cond,self.std_cond = self._EA__getCopulaParams(n_size,bin_1_limit,bin_step)

    def getContours(self, time_ss, time_r, nb_steps = 1000):
        '''WDRT Extreme Sea State Rosenblatt Copula Contour function
        This function calculates environmental contours of extreme sea states using
        a Rosenblatt transformation and the inverse first-order reliability
        method.

        Parameters
        ___________
        time_ss : float
            Sea state duration (hours) of measurements in input.
        time_r : np.array
            Desired return period (years) for calculation of environmental
            contour, can be a scalar or a vector.
        nb_steps : float
            Discretization of the circle in the normal space used for
            inverse FORM calculation.

        Returns
        -------
        Hs_Return : np.array
            Calculated Hs values along the contour boundary following
            return to original input orientation.
        T_Return : np.array
           Calculated T values along the contour boundary following
           return to original input orientation.
        nb_steps : float
            Discretization of the circle in the normal space

        Example
        -------
        To obtain the contours for a NDBC buoy::
            import numpy as np
            import WDRT.ESSC as ESSC
            # Pull spectral data from NDBC website
            buoy = ESSC.buoy('46022')
            buoy.fetchFromWeb()

            # Declare required parameters
            depth = 391.4  # Depth at measurement point (m)


            # Create Environtmal Analysis object using above parameters
            Rosen46022 = ESSC.Rosenblatt(depth, buoy)

            # used for inverse FORM calculation
            Time_SS = 1.  # Sea state duration (hrs)
            Time_r = np.array([100])  # Return periods (yrs) of interest

            nb_steps = 1000.  # Enter discretization of the circle in the normal space

            # Contour generation example
            Hs_Return, T_Return = Rosen46022.getContours(Time_SS, Time_r, nb_steps)
        '''
        self.time_ss = time_ss
        self.time_r = time_r
        self.nb_steps = nb_steps

        p_f = 1 / (365 * (24 / time_ss) * time_r)
        beta = stats.norm.ppf((1 - p_f), loc=0, scale=1)  # Reliability
        theta = np.linspace(0, 2 * np.pi, num = nb_steps)
        # Vary U1, U2 along circle sqrt(U1^2+U2^2)=beta
        U1 = beta * np.cos(theta)
        U2 = beta * np.sin(theta)

        comp_1 = stats.exponweib.ppf(stats.norm.cdf(U1),a=self.para_dist_1[0],c=self.para_dist_1[1],loc=self.para_dist_1[2],scale=self.para_dist_1[3])

        lamda_cond=self.mean_cond[0]+self.mean_cond[1]*comp_1+self.mean_cond[2]*comp_1**2+self.mean_cond[3]*comp_1**3      # mean of Ln(T) as a function of Hs
        sigma_cond=self.std_cond[0]+self.std_cond[1]*comp_1+self.std_cond[2]*comp_1**2                                # Standard deviation of Ln(T) as a function of Hs

        comp_2_Rosenblatt = stats.lognorm.ppf(stats.norm.cdf(U2),s=sigma_cond,loc=0,scale=np.exp(lamda_cond))  # lognormal inverse

        Hs_Return = comp_1
        T_Return = comp_2_Rosenblatt

        self.Hs_ReturnContours = Hs_Return
        self.T_ReturnContours = T_Return
        return Hs_Return, T_Return

    def getSamples(self):
        raise NotImplementedError

    def _saveParams(self, groupObj):
        groupObj.create_dataset('n_size', data=self.n_size)
        groupObj.create_dataset('bin_1_limit', data=self.bin_1_limit)
        groupObj.create_dataset('bin_step', data=self.bin_step)
        groupObj.create_dataset('para_dist_1', data=self.para_dist_1)
        groupObj.create_dataset('para_dist_2', data=self.para_dist_2)
        groupObj.create_dataset('mean_cond', data=self.mean_cond)
        groupObj.create_dataset('std_cond', data=self.std_cond)


class ClaytonCopula(EA):
    def __init__(self, buoy, n_size=40., bin_1_limit=1., bin_step=0.25):
        '''
        Parameters
        ___________
            depth : int
                Depth at measurement point (m)
            buoy : NDBCData
                ESSC.Buoy Object
            n_size: float
                minimum bin size used for Copula contour methods
            bin_1_limit: float
                maximum value of Hs for the first bin
            bin_step: float
                overlap interval for each bin
        '''
        self.method = "Clayton Copula"
        self.buoy = buoy
        self.n_size = n_size
        self.bin_1_limit = bin_1_limit
        self.bin_step = bin_step

        self.Hs_ReturnContours = None
#        self.Hs_SampleCA = None
#        self.Hs_SampleFSS = None

        self.T_ReturnContours = None
#        self.T_SampleCA = None
#        self.T_SampleFSS = None

#        self.Weight_points = None

#        self.coeff, self.shift, self.comp1_params, self.sigma_param, self.mu_param = self.__generateParams(size_bin)
        self.para_dist_1,self.para_dist_2,self.mean_cond,self.std_cond = self._EA__getCopulaParams(n_size,bin_1_limit,bin_step)

    def getContours(self, time_ss, time_r, nb_steps = 1000):
        '''WDRT Extreme Sea State Clayton Copula Contour function
        This function calculates environmental contours of extreme sea states using
        a Clayton copula and the inverse first-order reliability
        method.

        Parameters
        ___________
        time_ss : float
            Sea state duration (hours) of measurements in input.
        time_r : np.array
            Desired return period (years) for calculation of environmental
            contour, can be a scalar or a vector.
        nb_steps : float
            Discretization of the circle in the normal space used for
            inverse FORM calculation.

        Returns
        -------
        Hs_Return : np.array
            Calculated Hs values along the contour boundary following
            return to original input orientation.
        T_Return : np.array
           Calculated T values along the contour boundary following
           return to original input orientation.
        nb_steps : float
            Discretization of the circle in the normal space

        Example
        -------
        To obtain the contours for a NDBC buoy::
            import numpy as np
            import WDRT.ESSC as ESSC
            # Pull spectral data from NDBC website
            buoy = ESSC.buoy('46022')
            buoy.fetchFromWeb()

            # Declare required parameters
            depth = 391.4  # Depth at measurement point (m)


            # Create Environtmal Analysis object using above parameters
            Clayton46022 = ESSC.ClaytonCopula(depth, buoy)

            # used for inverse FORM calculation
            Time_SS = 1.  # Sea state duration (hrs)
            Time_r = np.array([100])  # Return periods (yrs) of interest

            nb_steps = 1000.  # Enter discretization of the circle in the normal space

            # Contour generation example
            Hs_Return, T_Return = Clayton46022.getContours(Time_SS, Time_r, nb_steps)
        '''
        self.time_ss = time_ss
        self.time_r = time_r
        self.nb_steps = nb_steps

        p_f = 1 / (365 * (24 / time_ss) * time_r)
        beta = stats.norm.ppf((1 - p_f), loc=0, scale=1)  # Reliability
        theta = np.linspace(0, 2 * np.pi, num = nb_steps)
        # Vary U1, U2 along circle sqrt(U1^2+U2^2)=beta
        U1 = beta * np.cos(theta)
        U2 = beta * np.sin(theta)

        comp_1 = stats.exponweib.ppf(stats.norm.cdf(U1),a=self.para_dist_1[0],c=self.para_dist_1[1],loc=self.para_dist_1[2],scale=self.para_dist_1[3])

        tau = stats.kendalltau(self.buoy.T,self.buoy.Hs)[0] # Calculate Kendall's tau
        theta_clay = (2.*tau)/(1.-tau)

        z2_Clay=((1.-stats.norm.cdf(U1)**(-theta_clay)+stats.norm.cdf(U1)**(-theta_clay)/stats.norm.cdf(U2))**(theta_clay/(1.+theta_clay)))**(-1./theta_clay)
        comp_2_Clayton = stats.lognorm.ppf(z2_Clay,s=self.para_dist_2[1],loc=0,scale=np.exp(self.para_dist_2[0])) #lognormalinverse

        Hs_Return = comp_1
        T_Return = comp_2_Clayton

        self.Hs_ReturnContours = Hs_Return
        self.T_ReturnContours = T_Return
        return Hs_Return, T_Return

    def getSamples(self):
        raise NotImplementedError

    def _saveParams(self, groupObj):
        groupObj.create_dataset('n_size', data=self.n_size)
        groupObj.create_dataset('bin_1_limit', data=self.bin_1_limit)
        groupObj.create_dataset('bin_step', data=self.bin_step)
        groupObj.create_dataset('para_dist_1', data=self.para_dist_1)
        groupObj.create_dataset('para_dist_2', data=self.para_dist_2)
        groupObj.create_dataset('mean_cond', data=self.mean_cond)
        groupObj.create_dataset('std_cond', data=self.std_cond)


class GumbelCopula(EA):
    def __init__(self, buoy, n_size=40., bin_1_limit=1., bin_step=0.25,Ndata = 1000):
        '''
        Parameters
        ___________
            depth : int
                Depth at measurement point (m)
            buoy : NDBCData
                ESSC.Buoy Object
            n_size: float
                minimum bin size used for Copula contour methods
            bin_1_limit: float
                maximum value of Hs for the first bin
            bin_step: float
                overlap interval for each bin
        '''
        self.method = "Gumbel Copula"
        self.buoy = buoy
        self.n_size = n_size
        self.bin_1_limit = bin_1_limit
        self.bin_step = bin_step

        self.Hs_ReturnContours = None
#        self.Hs_SampleCA = None
#        self.Hs_SampleFSS = None
        self.T_ReturnContours = None
#        self.T_SampleCA = None
#        self.T_SampleFSS = None
#        self.Weight_points = None

#        self.coeff, self.shift, self.comp1_params, self.sigma_param, self.mu_param = self.__generateParams(size_bin)
        self.Ndata = Ndata
        self.min_limit_2 = 0.
        self.max_limit_2 = np.ceil(np.amax(self.buoy.T)*2)
        self.para_dist_1,self.para_dist_2,self.mean_cond,self.std_cond = self._EA__getCopulaParams(n_size,bin_1_limit,bin_step)

    def getContours(self, time_ss, time_r, nb_steps = 1000):
        '''WDRT Extreme Sea State Gumbel Copula Contour function
        This function calculates environmental contours of extreme sea states using
        a Gumbel copula and the inverse first-order reliability
        method.

        Parameters
        ___________
        time_ss : float
            Sea state duration (hours) of measurements in input.
        time_r : np.array
            Desired return period (years) for calculation of environmental
            contour, can be a scalar or a vector.
        nb_steps : float
            Discretization of the circle in the normal space used for
            inverse FORM calculation.

        Returns
        -------
        Hs_Return : np.array
            Calculated Hs values along the contour boundary following
            return to original input orientation.
        T_Return : np.array
           Calculated T values along the contour boundary following
           return to original input orientation.
        nb_steps : float
            Discretization of the circle in the normal space

        Example
        -------
        To obtain the contours for a NDBC buoy::
            import numpy as np
            import WDRT.ESSC as ESSC
            # Pull spectral data from NDBC website
            buoy = ESSC.buoy('46022')
            buoy.fetchFromWeb()

            # Declare required parameters
            depth = 391.4  # Depth at measurement point (m)
            size_bin = 250.  # Enter chosen bin size

            # Create Environtmal Analysis object using above parameters
            Gumbel46022 = ESSC.GumbelCopula(depth, size_bin, buoy)

            # used for inverse FORM calculation
            Time_SS = 1.  # Sea state duration (hrs)
            Time_r = np.array([100])  # Return periods (yrs) of interest

            nb_steps = 1000.  # Enter discretization of the circle in the normal space

            # Contour generation example
            Hs_Return, T_Return = Gumbel46022.getContours(Time_SS, Time_r, nb_steps)
        '''
        self.time_ss = time_ss
        self.time_r = time_r
        self.nb_steps = nb_steps

        p_f = 1 / (365 * (24 / time_ss) * time_r)
        beta = stats.norm.ppf((1 - p_f), loc=0, scale=1)  # Reliability
        theta = np.linspace(0, 2 * np.pi, num = nb_steps)
        # Vary U1, U2 along circle sqrt(U1^2+U2^2)=beta
        U1 = beta * np.cos(theta)
        U2 = beta * np.sin(theta)

        comp_1 = stats.exponweib.ppf(stats.norm.cdf(U1),a=self.para_dist_1[0],c=self.para_dist_1[1],loc=self.para_dist_1[2],scale=self.para_dist_1[3])

        tau = stats.kendalltau(self.buoy.T,self.buoy.Hs)[0] # Calculate Kendall's tau
        theta_gum = 1./(1.-tau)

        fi_u1=stats.norm.cdf(U1);
        fi_u2=stats.norm.cdf(U2);
        x2 = np.linspace(self.min_limit_2,self.max_limit_2,self.Ndata)
        z2 = stats.lognorm.cdf(x2,s=self.para_dist_2[1],loc=0,scale=np.exp(self.para_dist_2[0]))

        comp_2_Gumb = np.zeros(nb_steps)
        for k in range(0,int(nb_steps)):
            z1 = np.linspace(fi_u1[k],fi_u1[k],self.Ndata)
            Z = np.array((z1,z2))
            Y = self.__gumbelCopula(Z, theta_gum) # Copula density function
            Y =np.nan_to_num(Y)
            p_x2_x1 = Y*(stats.lognorm.pdf(x2, s = self.para_dist_2[1], loc=0, scale = np.exp(self.para_dist_2[0]))) # pdf 2|1, f(comp_2|comp_1)=c(z1,z2)*f(comp_2)
            dum = np.cumsum(p_x2_x1)
            cdf = dum/(dum[self.Ndata-1]) # Estimate CDF from PDF
            table = np.array((x2, cdf)) # Result of conditional CDF derived based on Gumbel copula
            table = table.T
            for j in range(self.Ndata):
                if fi_u2[k] <= table[0,1]:
                    comp_2_Gumb[k] = min(table[:,0])
                    break
                elif fi_u2[k] <= table[j,1]:
                    comp_2_Gumb[k] = (table[j,0]+table[j-1,0])/2
                    break
                else:
                    comp_2_Gumb[k] = table[:,0].max()

        Hs_Return = comp_1
        T_Return = comp_2_Gumb

        self.Hs_ReturnContours = Hs_Return
        self.T_ReturnContours = T_Return
        return Hs_Return, T_Return

    def getSamples(self):
        raise NotImplementedError

    def _saveParams(self, groupObj):
        groupObj.create_dataset('Ndata', data=self.Ndata)
        groupObj.create_dataset('min_limit_2', data=self.min_limit_2)
        groupObj.create_dataset('max_limit_2', data=self.max_limit_2)
        groupObj.create_dataset('n_size', data=self.n_size)
        groupObj.create_dataset('bin_1_limit', data=self.bin_1_limit)
        groupObj.create_dataset('bin_step', data=self.bin_step)
        groupObj.create_dataset('para_dist_1', data=self.para_dist_1)
        groupObj.create_dataset('para_dist_2', data=self.para_dist_2)
        groupObj.create_dataset('mean_cond', data=self.mean_cond)
        groupObj.create_dataset('std_cond', data=self.std_cond)

    def __gumbelCopula(self, u, alpha):
        ''' Calculates the Gumbel copula density
        Parameters
        ----------
        u: np.array
                    Vector of equally spaced points between 0 and twice the
                    maximum value of T.
       alpha: float
                    Copula parameter. Must be greater than or equal to 1.
        Returns
        -------
       y: np.array
                   Copula density function.
        '''
        np.seterr(all='ignore')        
        v = -np.log(u)
        v = np.sort(v, axis=0)
        vmin = v[0, :]
        vmax = v[1, :]
        nlogC = vmax * (1 + (vmin / vmax) ** alpha) ** (1 / alpha)
        y = (alpha - 1 +nlogC)*np.exp(-nlogC+np.sum((alpha-1)*np.log(v)+v, axis =0) +(1-2*alpha)*np.log(nlogC))
        np.seterr(all='warn')

        return(y)


class Buoy:
    '''
    Attributes
    __________
    swdList : list
        List that contains numpy arrays of the spectral wave density data,
        separated by year.
    freqList: list
        List that contains numpy arrays that contain the frequency values
        for each year
    dateList : list
        List that contains numpy arrays of the date values for each line of
        spectral data, separated by year
    Hs : list
        Significant wave height.
    T : list
        Energy period.
    dateNum : list
        List of datetime objects.
    '''



    def __init__(self, buoyNum, savePath = './Data/'):

        '''
        Parameters
        ___________
            buoyNum : string
                device number for desired buoy
            savePath : string
                relative path where the data read from ndbc.noaa.gov will be stored


        '''
        self.swdList = []
        self.freqList = []
        self.dateList = []
        self.Hs = []
        self.T = []
        self.dateNum = []

        self.buoyNum = buoyNum
        self.savePath = savePath


        if not os.path.exists(savePath):
          os.makedirs(savePath)



    def fetchFromWeb(self, saveType="txt", savePath=None):

        '''Searches ndbc.noaa.gov for the historical spectral wave density
        data of a given device and writes the annual files from the website
        to a single .txt file, and stores the values in the swdList, freqList,
        and dateList member variables.

        Parameters
        ----------
        saveType: string
            If set to to "h5", the data will be saved in a compressed .h5
            file
            If set to "txt", the data will be stored in a raw .txt file
            Otherwise, a file will not be created
        savePath : string
            Relative path to place directory with data files.
        Example
        _________
        >>> import WDRT.ESSC as ESSC
        >>> buoy = ESSC.Buoy(46022)
        >>> buoy.fetchFromWeb()
        '''
        numLines = 0
        numCols = 0
        numDates = 0
        dateVals = []
        spectralVals = []
        if savePath == None:
            savePath = self.savePath

        url = "http://www.ndbc.noaa.gov/station_history.php?station=%s" % (self.buoyNum)
        ndbcURL = requests.get(url,proxies = {"http":"http://wwwproxy.sandia.gov:80"})
        ndbcURL.raise_for_status()
        ndbcHTML = bs4.BeautifulSoup(ndbcURL.text, "lxml")
        headers = ndbcHTML.findAll("b", text="Spectral wave density data: ")

        if len(headers) == 0:
            raise Exception("Spectral wave density data for given buoy not found")


        if len(headers) == 2:
            headers = headers[1]
        else:
            headers = headers[0]

        links = [a["href"] for a in headers.find_next_siblings("a", href=True)]

        if(saveType is 'txt'):
            # Grab the device number so the filename is more specific
            saveDir = os.path.join(self.savePath, 'NDBC%s' % (self.buoyNum))
            print "Saving in :", saveDir
            if not os.path.exists(saveDir):
                os.makedirs(saveDir)

        if(saveType is "h5"):
            saveDir = os.path.join(self.savePath, 'NDBC%s-raw.h5' %(self.buoyNum))
            print "Saving in :", saveDir
            f = h5py.File(saveDir, 'w')

        for link in links:
            dataLink = "http://ndbc.noaa.gov" + link
            year = int(re.findall("[0-9]+", link)[1])
            if(saveType is 'txt'):
            #certain years have multiple files marked with the letter 'b'
                if ('b' + str(year)) not in link:
                    swdFile = open(os.path.join(saveDir, "SWD-%s-%d.txt" %
                                   (self.buoyNum, year)), 'w')
                else:
                    swdFile = open(os.path.join(saveDir, "SWD-%s-%s.txt" %
                                   (self.buoyNum, str(year) + 'b')), 'w')

            if(saveType is 'h5'):
                if ('b' + str(year)) not in link:
                    dataSetName = str(("SWD-%s-%d" %
                                   (self.buoyNum, year)))
                else:
                    dataSetName = str(("SWD-%s-%s" %
                                   (self.buoyNum, str(year) + 'b')))


            fileName = dataLink.replace('download_data', 'view_text_file')
            data = urllib2.urlopen(fileName)
            print "Reading from:", data.geturl()



            # dates after 2004 contain a time-value for minutes
            if (year > 2004):
                numDates = 5
            else:
                numDates = 4

            #First Line of every file contains the frequency data
            frequency = data.readline()
            if (saveType is "txt"):
                swdFile.write(frequency)
            frequency = np.array(frequency.split()[numDates:], dtype = np.float)


            for line in data:
                if (saveType is "txt"):
                    swdFile.write(line)
                currentLine = line.split()
                numCols = len(currentLine)

                if float(currentLine[numDates+1]) < 999:
                    numLines += 1
                    for j in range(numDates):
                        dateVals.append(currentLine[j])
                    for j in range(numCols - numDates):
                        spectralVals.append(currentLine[j + numDates])

            dateValues = np.array(dateVals, dtype=np.int)
            spectralValues = np.array(spectralVals, dtype=np.float)

            dateValues = np.reshape(dateValues, (numLines, numDates))
            spectralValues = np.reshape(spectralValues, (numLines,
                                                         (numCols - numDates)))

            if(saveType is "h5"):
                f.create_dataset(str(dataSetName) + "-date_values", data = dateValues,compression = "gzip")
                f.create_dataset(str(dataSetName + "-frequency"),data=frequency,compression = "gzip")
                f.create_dataset(dataSetName,data=spectralValues,compression = "gzip")

            del dateVals[:]
            del spectralVals[:]

            numLines = 0
            numCols = 0
            self.swdList.append(spectralValues)
            self.freqList.append(frequency)
            self.dateList.append(dateValues)

            if(saveType is "txt"):
                swdFile.close()
        self._prepData()

    def loadFromText(self, dirPath=None):
        '''Loads NDBC data previously downloaded to a series of text files in the
        specified directory.

        Parameters
        ----------
            dirPath : string
                Relative path to directory containing NDBC text files (created by
                NBDCdata.fetchFromWeb). If left blank, the method will search
                all directories for the data using the current directory as
                the root.


        Example
        -------
        To load data from previously downloaded files

        >>> import WDRT.ESSC as ESSC
        >>> buoy = ESSC.buoy(46022)
        >>> buoy.loadFromText('./Data/NDBC460022')
        '''
        dateVals = []
        spectralVals = []
        numLines = 0

        if dirPath is None:
            for dirpath, subdirs, files in os.walk('.'):
                for dirs in subdirs:
                    if ("NDBC%s" % self.buoyNum) in dirs:
                        dirPath = os.path.join(dirpath,dirs)
                        break
        if dirPath is None:
            raise IOError("Could not find directory containing NDBC data")

        fileList = glob.glob(os.path.join(dirPath,'SWD*.txt'))

        if len(fileList) == 0:
            raise IOError("No NDBC data files found in " + dirPath)

        for fileName in fileList:
            print 'Reading from: %s' % (fileName)
            f = open(fileName, 'r')
            frequency = f.readline().split()
            numCols = len(frequency)
            if frequency[4] == 'mm':
                frequency = np.array(frequency[5:], dtype=np.float)
                numTimeVals = 5

            else:
                frequency = np.array(frequency[4:], dtype=np.float)
                numTimeVals = 4

            for line in f:
                currentLine = line.split()
                if float(currentLine[numTimeVals + 1]) < 999:
                    numLines += 1
                    for i in range(numTimeVals):
                        dateVals.append(currentLine[i])
                    for i in range(numCols - numTimeVals):
                        spectralVals.append(currentLine[i + numTimeVals])

            dateValues = np.array(dateVals, dtype=np.int)
            spectralValues = np.array(spectralVals, dtype=np.double)
            dateValues = np.reshape(dateValues, (numLines, numTimeVals))
            spectralValues = np.reshape(
                spectralValues, (numLines, (numCols - numTimeVals)))

            del dateVals[:]
            del spectralVals[:]

            numLines = 0
            numCols = 0
            self.swdList.append(spectralValues)
            self.freqList.append(frequency)
            self.dateList.append(dateValues)
        self._prepData()

    def loadFromH5(self, fileName):
        """
        Loads NDBCdata previously saved in a .h5 file

        Parameters
        ----------
            fileName : string
                Name of the .h5 file to load data from.
        Example
        -------
        To load data from previously downloaded files

        >>> import WDRT.ESSC as ESSC
        >>> buoy = ESSC.Buoy(46022)
        >>> buoy.loadFromH5("./Data")
        """
        _, file_extension = os.path.splitext(fileName)
        if not file_extension:
            fileName = fileName + '.h5'
        print "Reading from: ", fileName
        try:
            f = h5py.File(fileName, 'r')
        except IOError:
            raise IOError("Could not find file: " + fileName)
        self.Hs = np.array(f['buoy_Data/Hs'][:])
        self.T = np.array(f['buoy_Data/Te'][:])
        self.dateNum = np.array(f['buoy_Data/dateNum'][:])
        print "----> SUCCESS"

    def saveData(self, fileName=None):
        '''
        Saves NDBCdata to hdf5 file.

        Parameters
        ----------
            savePath : string
                Relative path for desired file.
        '''
        if (fileName is None):
            fileName = 'NDBC' + str(self.buoy.buoyNum) + '.h5'
        else:
            _, file_extension = os.path.splitext(fileName)
            if not file_extension:
                fileName = fileName + '.h5'
        f = h5py.File(fileName, 'w')
        self._saveData(f)

    def _saveData(self, fileObj):
        if(self.Hs is not None):
            gbd = fileObj.create_group('buoy_Data')
            f_Hs = gbd.create_dataset('Hs', data=self.Hs)
            f_Hs.attrs['units'] = 'm'
            f_Hs.attrs['description'] = 'significant wave height'
            f_T = gbd.create_dataset('Te', data=self.T)
            f_T.attrs['units'] = 'm'
            f_T.attrs['description'] = 'energy period'
            f_dateNum = gbd.create_dataset('dateNum', data=self.dateNum)
            f_dateNum.attrs['description'] = 'datenum'
        else:
            RuntimeError('Buoy object contains no data')

    def _prepData(self):
        '''Runs _getStats and _getDataNums for full set of data, then removes any
        NaNs.
        '''
        n = len(self.swdList)
        Hs = []
        T = []
        dateNum = []
        for ii in range(n):
            tmp1, tmp2 = _getStats(self.swdList[ii], self.freqList[ii])
            Hs.extend(tmp1)
            T.extend(tmp2)
            dateNum.extend(_getDateNums(self.dateList[ii]))
        Hs = np.array(Hs, dtype=np.float)
        T = np.array(T, dtype=np.float)
        dateNum = np.array(dateNum, dtype=np.float)

        # Removing NaN data, assigning T label depending on input (Te or Tp)
        Nanrem = np.logical_not(np.isnan(T) | np.isnan(Hs))
        # Find NaN data in Hs or T
        dateNum = dateNum[Nanrem]  # Remove any NaN data from DateNum
        Hs = Hs[Nanrem]  # Remove any NaN data from Hs
        T = T[Nanrem]  # Remove any NaN data from T
        self.Hs = Hs
        self.T = T
        self.dateNum = dateNum
        return Hs, T, dateNum

def _getDateNums(dateArr):
    '''datetime objects

    Parameters
    ----------
        dateArr : np.array
            Array of a specific years date vals from NDBC.fetchFromWeb

    Returns
    -------
        dateNum : np.array
            Array of datetime objects.
    '''
    dateNum = []
    for times in dateArr:
        if  times[0] < 1900:
            times[0] = 1900 + times[0]
        if times[0] < 2005:
            dateNum.append(date.toordinal(datetime(times[0], times[1],
                                                   times[2], times[3])))
        else:
            dateNum.append(date.toordinal(datetime(times[0], times[1],
                                                   times[2], times[3],
                                                   times[4])))
    return dateNum

def _getStats(swdArr, freqArr):
        '''Significant wave height and energy period

        Parameters
        ----------
            swdArr : np.array
                Numpy array of the spectral wave density data for a specific year
            freqArr: np.array
                Numpy array that contains the frequency values for a specific year

        Returns
        -------
            Hm0 : list
                Significant wave height.
            Te : list
                Energy period.
        '''
        np.seterr(divide='ignore')

        Hm0 = []
        T = []

        for line in swdArr:
            m_1 = np.trapz(line * freqArr ** (-1), freqArr)
            m0 = np.trapz(line, freqArr)
            Hm0.append(4.004 * m0 ** 0.5)
            T.append(m_1 / m0)
        np.seterr(divide='warn')

        return Hm0, T
