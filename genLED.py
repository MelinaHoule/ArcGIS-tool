## Created by Melina Houle
## Feb 22, 2014
#############################################################################
##SPECIFICATIONS
# This script downloaded the NHN 1:50,000 data intersecting a study region needed to create LED 
# Prior to launch the script, the NHN index must be downloaded 
# The NHN index will be used to identify workunits intersecting the study region of interest
# The NHN index can be found at : http://www.geobase.ca/geobase/en/data/nhn/national-index.html

import zipfile, sys, os, csv, shutil, os.path, arcpy, time, timeit
from ftplib import FTP
from arcpy import env
from arcpy.sa import *
from os.path import join


currentDir = os.getcwd()

## Location NHN index shapefile
NHNindex = currentDir + "/index/NHN_INDEX_WORKUNIT.shp"
## Location Study Region shapefile
studyregion = currentDir + "/shp/NWBLCC_AoA_fda_diss.shp"
## Location output coordinate system
outCS = currentDir + "/proj/NWB_LCC_proj.prj"

####################################
##    SET FTP PARAMETERS
####################################
# Geobase FTP site
ftpSite = "ftp2.cits.rncan.gc.ca"
# Change if you want other GIS format
ftpDir = "/pub/geobase/official/nhn_rhn/gdb_en/"
# Logon to FTP site
ftp = FTP(ftpSite)
ftp.login('anonymous', 'beacons')
##---------------------------------
####################################
##    SET LED PARAMETERS
####################################
buffer = 3000
cellRes = 250
searchRadius = 2820.94461
## Set LED output name
outLED = "led_250_25.tif"

##----------------------------------------------------------------
##NOTHING SHOULD BE CHANGED BELOW THIS LINE
##----------------------------------------------------------------
##--------------------
## DIRECTORIES
##--------------------
## Location of destination folder
outDirectory = currentDir + "/output"
zipFileOutputDir = outDirectory + "/zip"
unzipOutputDir = outDirectory + "/unzip"
nhnOutputDir = outDirectory + "/nhn_features"
tempOutputDir = outDirectory + "/temp"
wlineOutputDir = outDirectory + "/waterlines"
FinalOutputDir = outDirectory + "/Final"
###################################################################################################
def prepStudyRegion(studyregion,buffer,outDir,cellres,outCS):
    print "Step 1 : Preparing study region"
    if os.path.exists(tempOutputDir):
        shutil.rmtree(tempOutputDir)
    os.makedirs(tempOutputDir)
    if os.path.exists(FinalOutputDir):
        shutil.rmtree(FinalOutputDir)
    os.makedirs(FinalOutputDir)

    ## Add a buffer around the study region to allow moving window across the ecoregion (LED methodology)
    outFile = tempOutputDir + "/studyregion_pj.shp"
    arcpy.Buffer_analysis(studyregion,outFile,buffer)
    ## Transform the study region into an empty raster
    arcpy.env.extent = outFile
    outConstRaster = CreateConstantRaster(1, "INTEGER", cellres)
    rastExtent = outDir + "/extent.tif"
    outConstRaster.save(rastExtent)
    arcpy.DefineProjection_management(rastExtent, outCS)
    return rastExtent
###################################################################################################
def downloadZipNHN(index,tempDir,studyregion):
    print "Step 2 : Downloding zip NHN from Geodatabase ftp site"
    ## Createa FeatureLayer to allow selection 
    arcpy.MakeFeatureLayer_management(index, "flayer")

    ## Select workunits intersecting the Study Region
    copyFile = tempDir + "/NHN_index_studyregion.shp"
    arcpy.SelectLayerByLocation_management ("flayer", "INTERSECT", studyregion)
    arcpy.CopyFeatures_management("flayer", copyFile)
    arcpy.SelectLayerByAttribute_management( "flayer", "CLEAR_SELECTION")
    arcpy.Delete_management("flayer", "FeatureLayer")

    ## List workunits intersecting the study region
    id = [row[0] for row in arcpy.da.SearchCursor(copyFile, "WSCMDA")]
    unique_id = set(id)
    workunit = [row[0] for row in arcpy.da.SearchCursor(copyFile, "DATASETNAM")]
    
    ## Start the download
    ## Download from multiple directories
    if os.path.exists(zipFileOutputDir):
        shutil.rmtree(zipFileOutputDir)
    os.makedirs(zipFileOutputDir)

    downloadCount = 0
    for i in unique_id:
        # Make and change directory
        os.makedirs(zipFileOutputDir + "/" + str(i) + "/")
        os.chdir(zipFileOutputDir + "/" + str(i) + "/")
        # Logon to FTP site
        ftp = FTP(ftpSite)
        ftp.login('anonymous', 'beacons')
        ftp.cwd(ftpDir + str(i) + "/")
        dir = ftp.nlst('.')
        for file in dir:
        	# Download all zip files in directory
            if any(file[8:15].upper() in wu for wu in workunit):
                downloadCount = downloadCount + 1
                f = open(file, 'wb')
                ftp.retrbinary('RETR ' + file, f.write, 1024)      
        ftp.quit()      
    print "Number of workunits to download from NRCAN ftp site = " + str(len(workunit))
    print "Number of workunits downloaded from NRCAN ftp site = " + str(downloadCount) 
###################################################################################################
def unzipNHN(zipDir,unzipDir):
    print "Step 3 : Unzipping workunit directories intersection the study region"
    errorList = ""
    unit = os.listdir(zipDir)
    
    if os.path.exists(unzipOutputDir):
        shutil.rmtree(unzipOutputDir)
    os.makedirs(unzipOutputDir)
    for u in unit:  
        zipFile = os.listdir(zipDir + "/" + u)
        for f in zipFile:
            inFile = zipDir + "/" + u + "/" + f
            try:
                sourceZip = zipfile.ZipFile(inFile, 'r')
                sourceZip.extractall(unzipDir)
                sourceZip.close()
            except:
                print f
                errorList.append(str(f))
###################################################################################################
def genWaterlineFromNHN(unzipDir,tempDir):
    print "Step 4 : Reprojecting and converting features to line to genrerate LED"
    if os.path.exists(nhnOutputDir):
        shutil.rmtree(nhnOutputDir)
    os.makedirs(nhnOutputDir)
    if os.path.exists(wlineOutputDir):
        shutil.rmtree(wlineOutputDir)
    os.makedirs(wlineOutputDir)

    ## Create LED from waterbodies and island intersection the study region
    ## Loop through workunits directories and extract waterbodies and island...")
    unit = os.listdir(unzipDir)
    for u in unit:  
        ## Set the workspace
        arcpy.env.workspace = unzipDir + "/" + u
        dataset = arcpy.ListDatasets()
        for d in dataset:
            arcpy.env.workspace = unzipDir + "/" + u + "/" + d
            tables = arcpy.ListFeatureClasses()
            ##-----------------------------------------------------
            ## Reproject and convert polygons to polylines for waterbodies and island
            for t in tables:        
                if t.find('ISLAND')!= -1 or t.find('WATERBODY')!= -1 :
                    if t.find('ISLAND')!= -1:
                        feature = "island"
                    if t.find('WATERBODY')!= -1:
                        feature = "waterbody"
                    inFile = unzipDir + "/" + u + "/" + d + "/" + t
                    count = str(arcpy.GetCount_management(inFile))
                    ## Make sure the table is not empty
                    if count > '0':
                        outFile = nhnOutputDir + "/" + u[0:12] + feature + ".shp"
                        arcpy.Project_management(inFile, outFile, outCS)                      
                        inFile = nhnOutputDir + "/" + u[0:12] + feature + ".shp"
                        outFile = nhnOutputDir + "/line_" + u[0:12] + feature + ".shp"
                        arcpy.PolygonToLine_management(inFile, outFile,"IDENTIFY_NEIGHBORS")
                        ## Delete inside polygons from the conversion to avoid over estimation of edges
                        inFile = nhnOutputDir + "/line_" + u[0:12] + feature + ".shp"
                        outFile = wlineOutputDir + "/" + u[0:12] + feature + ".shp"
                        arcpy.MakeFeatureLayer_management(inFile, "lyr")
                        arcpy.SelectLayerByAttribute_management("lyr", "NEW_SELECTION", ' "LEFT_FID" = -1 OR "RIGHT_FID" =-1')
                        arcpy.CopyFeatures_management("lyr", outFile)
                        arcpy.SelectLayerByAttribute_management("lyr", "CLEAR_SELECTION")
                        arcpy.Delete_management("lyr","FeatureLayer")
                        
    arcpy.env.workspace = wlineOutputDir
    waterlineList = arcpy.ListFeatureClasses()
    arcpy.CreateFileGDB_management(tempDir, "waterlines.gdb")
    waterLine = tempDir + "/waterlines.gdb/waterlines"
    arcpy.Merge_management(waterlineList, waterLine)
    #shutil.rmtree(nhnOutputDir)
    #shutil.rmtree(unzipOutputDir)
    #shutil.rmtree(wlineOutputDir)
    #shutil.rmtree(zipOutputDir)
    return waterLine
#####################################################################################
def genLED(lineFile,outDir,outLED,outExtent,resCell,scale):
    "Step 5 : Generating LED"
    ## Set extension and processing extent
    arcpy.env.snapRaster = outExtent
    ## Calculate LED using Line Density in ArcGIS Spatial Analyst toolbox
    outLDens = LineDensity(lineFile, "", cellRes, searchRadius, "SQUARE_KILOMETERS") 
    outLDens.save(tempOutputDir + "/" + outLED)

    ## Clip LED to the study region
    inFile = tempOutputDir + "/" + outLED
    outFile = outDir + "/" + outLED
    arcpy.Clip_management(inFile,"#",outFile, studyregion, "#", "ClippingGeometry")
    #shutil.rmtree(tempOutputDir)

#####################################################################################
##--------------------
## DATA PROCESSING 
##--------------------
## Active Spatial Analyst extension
arcpy.CheckOutExtension("Spatial")

try:
    rastExtent = prepStudyRegion(studyregion,str(buffer),tempOutputDir,cellRes,outCS)
    downloadZipNHN(NHNindex,tempOutputDir,studyregion)
    unzipNHN(zipFileOutputDir,unzipOutputDir)
    waterLine = genWaterlineFromNHN(unzipOutputDir,tempOutputDir)
    genLED(waterLine,FinalOutputDir,outLED,rastExtent,cellRes,searchRadius)
    print "Done"
except:
    print arcpy.GetMessage(0)