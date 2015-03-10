#############################################################################
# genStandardizedCriteria.py v1
# Date created: December 15 2014
# Author: Melina Houle
# Description: This script extract criteria needed in the Representation Analysis and standardized them to the right resolution and spatial projection
# It uses a list of criteria, standardizes the projection and clip it to the study region
# Prior to run the script, you will need to make sure all indicators listed exist
# You will also need to create an empty raster covering the entire area of assessment that will serve as anchor point.
# The creation of an anchor point will force all raster to align on the same grid
#############################################################################

import sys, os, shutil, os.path, arcpy
from arcpy import env
from arcpy.sa import *
from os.path import join

arcpy.env.overwriteOutput = True

##-------------------------------------------------
##       SET PARAMETERS
##-------------------------------------------------
currentDir = os.getcwd()

## Path the the Study Region (here it is ecoregion because of the small scale of the dataset)
studyregion = currentDir + "/shp/NWBLCC_AoA_fda_diss.shp"

## Path to criteria
LED = currentDir + "/grids/led_250_25.tif"
CMI = currentDir + "/grids/NORM_6190_CMI.asc"
GPP = currentDir + "/grids/MOD17A3_Science_GPP_mean_00_13.tif"
NALC = currentDir + "/grids/nalc.tif"

## Set output coordinate system
outCS = currentDir + "/proj/NWB_LCC_proj.prj"

## Set the list of criteria
criteriaList = [CMI, GPP, LED, NALC]
criteriaOutput = {CMI:"cmi_a2_6190", GPP:"gpp_0013", LED:"led", NALC:"nalc"}

## Resolution of the extent
resList = ["250", "1000"]
## Set resampling algorithm :"NEAREST","BILINEAR","CUBIC","MAJORITY"
resampleOutput = {CMI:"BILINEAR", GPP:"BILINEAR", LED:"BILINEAR", NALC:"MAJORITY"}

##----------------------------------------------------------------
##NOTHING SHOULD BE CHANGED BELOW THIS LINE
##----------------------------------------------------------------
##-----------------------------------------------------
##               CREATE DIRECTORIES
##-----------------------------------------------------
## Path to destination folder
outDirectory = currentDir + "/output"
if os.path.exists(outDirectory):
    try:
        shutil.rmtree(outDirectory)
    except:
        logFile = open(outDirectory + "/log.log", 'w')
        logFile.close()
        os.remove(outDirectory + "/log.log")
        shutil.rmtree(outDirectory)
os.makedirs(outDirectory)

## This is the dir where the temp file will be written
tempOutputDir = outDirectory + "/temp"
if os.path.exists(tempOutputDir):
    shutil.rmtree(tempOutputDir)
os.makedirs(tempOutputDir)

## This is the dir where the temp file will be written
FinalOutputDir = outDirectory + "/Final"
if os.path.exists(FinalOutputDir):
    shutil.rmtree(FinalOutputDir)
os.makedirs(FinalOutputDir)
#####################################################################################
def genExtent(inputFile,outExtent,resList,outDir):
    print "Process step 1 : Generate grid extent"
    print " Changing " + inputFile + " projection..."
    arcpy.Project_management(inputFile, outExtent, outCS)
    for res in resList:

        ## This is the dir where the temp file will be written
        outFolder = outDir + "/" + res + "m"
        if os.path.exists(outFolder):
            shutil.rmtree(outFolder)
        os.makedirs(outFolder)

        ## Set the processing extent
        arcpy.env.extent = outExtent

        outFile = outFolder + "/bnd_" + res + "m.tif"
        print " Generating " + res + "m extent" 
        arcpy.FeatureToRaster_conversion(outExtent, "FID", outFolder + "/bnd_" + res + "m.tif",int(res))
    return
#####################################################################################
def extractCriteria(criteriaList,resList,outExtent,outDir):
    print "Process step 2 : Generate criteria using the grid extent"
    for res in resList:
        print res + "m"
        outFolder = outDir + "/" + res + "m"
        snapRaster = outFolder + "/bnd_" + res + "m.tif"
        arcpy.env.snapRaster = snapRaster
           
        for criterion in criteriaList:
            print " Generating " + criteriaOutput[criterion] + "_" + res + "m"
            ## Clip to Study Region and reproject indicators to Alaska Albers projection
            outFile = tempOutputDir + "/" + criteriaOutput[criterion] + "_" + res + "_clip.tif"
            arcpy.Clip_management(criterion, "#", outFile,outExtent,"#","NONE")
            inFile = tempOutputDir + "/" + criteriaOutput[criterion] + "_" + res + "_clip.tif"
            outFile = tempOutputDir + "/" + criteriaOutput[criterion] + "_" + res + ".tif"
            ## Check if the raster needs to be resample
            cellSize = float(arcpy.GetRasterProperties_management(inFile, "CELLSIZEX").getOutput(0))
            if int(cellSize) >= int(res):
                ## Do not resample, just reproject
                arcpy.ProjectRaster_management(inFile, outFile, outCS, "", res)
            else:
                ## Reprojected and resample following a define methods
                arcpy.ProjectRaster_management(inFile, outFile, outCS,resampleOutput[criterion],res)

            inFile = tempOutputDir + "/" + criteriaOutput[criterion] + "_" + res + ".tif"
            outFile = outFolder + "/" + criteriaOutput[criterion] + ".tif"
            arcpy.env.extent = outFolder + "/bnd_" + res + "m.tif"
            arcpy.Clip_management(inFile, "#", outFile,outExtent,"99999","ClippingGeometry")    
    return
#####################################################################################
##----------------------------------------------------------------
##-------------------------------------------------
## DATA PROCESS
##-------------------------------------------------
try:
    clipExtent = tempOutputDir + "/studyregion.shp"
    genExtent(studyregion,clipExtent,resList,FinalOutputDir)
    extractCriteria(criteriaList,resList,clipExtent,FinalOutputDir)
except:
    print "Failed to process...\n"
    print "Error message: "  + arcpy.GetMessage(0) + "\n"

print "The script ended with no error message"
sys.exit()
    

