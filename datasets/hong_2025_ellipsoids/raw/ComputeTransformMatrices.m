%% Compute the transform matrices that aren't there
%
% Start from what is there.
%
% Need Psychtoolbox on your path. With ToolboxToolbox
% run this command.  Otherwise find it and put it on your
% path.
%{
    tbUse('Psychtoolbox-3');
%}

%% Clear and close
clear; close all;

%% Change directory to where the local calibration data should be
%
% You will need to do this in a machine specific way
cd('/Users/dhb/Documents/Python/wppmpy_public/local/data/upenn/hong_etal_2025/Calibration and transformation/Transformation matrices');

%% Matrices from paper Table S2, S6
M_RGB_To_W = [1.556 -1.364 -0.192
             -0.444 -1.364 1.808
              0.444 1.364 0.192];
M_DKL_To_W = [6.724 0.213 0.000
              0.076 1.221 0.000
              0.000 0.000 1.000];

%% Load in calibration file
calibration = load('B_monitor_dell_02242025.mat');
B_monitor = calibration.B_monitor;
S = [380 2 201];
wls = SToWls(S);

% Load in T_xyz1931.  This is scaled so that the output
% Y is in cd/m2.
xyz1931Data = load('T_xyz1931.mat');
T_xyz1931  = SplineCmf(xyz1931Data.S_xyz1931,683*xyz1931Data.T_xyz1931,S);
M_RGB_To_XYZ1931 = T_xyz1931*B_monitor;
M_XYZ1931_To_RGB = inv(M_RGB_To_XYZ1931);
writematrix(M_RGB_To_XYZ1931, 'M_RGBToXYZ1931_DELL_02242025_copy.csv');
writematrix(M_XYZ1931_To_RGB, 'M_XYZ1931ToRGB_DELL_02242025_copy.csv');
% From some piece of python code, matches up
% M_RGB_To_XYZ = np.array(
%     [
%         [76.38516071, 66.85493869, 35.97864653],
%         [40.65203296, 134.47469612, 15.54729592],
%         [5.55666539, 25.32010873, 186.44526690],
%     ]
% )

% Load in T_xyz2015. Also scaled by the 683 constant
xyz2015Data = load('T_xyzCIEPhys2.mat');
T_xyz2015 = SplineCmf(xyz2015Data.S_xyzCIEPhys2,683*xyz2015Data.T_xyzCIEPhys2,S);
M_RGB_To_XYZ2015 = T_xyz2015*B_monitor;
M_XYZ2015_To_RGB = inv(M_RGB_To_XYZ2015);
writematrix(M_RGB_To_XYZ2015, 'M_RGBToXYZ2015_DELL_02242025_copy.csv');
writematrix(M_XYZ2015_To_RGB, 'M_XYZ2015ToRGB_DELL_02242025_copy.csv');

% Load in cones
coneData = load('T_cones_ss2.mat');
T_cones = SplineCmf(coneData.S_cones_ss2,coneData.T_cones_ss2,S);
M_RGB_To_LMS = T_cones*B_monitor;
M_LMS_To_RGB = inv(M_RGB_To_LMS);
writematrix(M_RGB_To_LMS, 'M_RGBToLMS_DELL_02242025_copy.csv');
writematrix(M_LMS_To_RGB, 'M_LMSToRGB_DELL_02242025_copy.csv');

% Need to go through monitor primaries for these to be right
M_LMS_To_XYZ1931 = M_RGB_To_XYZ1931*M_LMS_To_RGB;
M_XYZ1931_To_LMS = inv(M_LMS_To_XYZ1931);
writematrix(M_LMS_To_XYZ1931, 'M_LMSToXYZ1931_DELL_02242025_copy.csv');
writematrix(M_XYZ1931_To_LMS, 'M_XYZ1931ToLMS_DELL_02242025_copy.csv');

% Go through monitor primaries for these to be right
M_LMS_To_XYZ2015 = M_RGB_To_XYZ2015*M_LMS_To_RGB;
M_XYZ2015_To_LMS = inv(M_LMS_To_XYZ2015);
writematrix(M_LMS_To_XYZ2015, 'M_LMSToXYZ2015_DELL_02242025_copy.csv');
writematrix(M_XYZ2015_To_LMS, 'M_XYZ2015ToLMS_DELL_02242025_copy.csv');



