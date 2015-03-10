# genCriteria4RepAnalysis v1
# Date created: January 23 2015
# Author: Mélina Houle 
# Description: This script contains ArcGIS function used to :
# 	-generate criteria classes according to a define number of classes and method
#	-compile the area of each classes per catchment
#	-assemble an output dbf table where all classes will be compiled 
#############################################################################

import sys, os, shutil, os.path, arcpy
from arcpy import env
from arcpy.sa import *

arcpy.env.overwriteOutput = True

##-------------------------------------------------
##       SET PARAMETERS
##-------------------------------------------------
currentDir = os.getcwd()

## Path to catchments shp and criteria TIF
catchments = currentDir + "/catchments/catch.shp"
LED = currentDir + "/criteria/led.tif"
CMI = currentDir + "/criteria/cmi.tif"
GPP = currentDir + "/criteria/gpp.tif"
NALC = currentDir + "/criteria/nalc.tif"

indicatorsGDB = "indicators.gdb"  ## Set name of temporary gdb 

## Set the list of criteria
conIndicatorList = [CMI, GPP, LED] ## List continuous indicators paths
conIndicatorName = {CMI:"CMI", GPP:"GPP", LED:"LED"} ## List continuous indicators output name
catIndicatorList = [NALC] ## List categorical indicators paths
catIndicatorName = {NALC:"NALC"} ## List categorical indicators output name

## Reclass parameters
catchID = "CATCHNUM" ## Unique catchment identifier
floatRast = ["LED"]  ## List indicators output name that uses raster pixel FLOAT type
method = "EQUAL_INTERVAL"  ## Set reclass parameters method (EQUAL_INTERVAL, EQUAL_AREA, NATURAL_BREAKS)
n = 20   ## Set reclass number of class

##----------------------------------------------------------------
##NOTHING SHOULD BE CHANGED BELOW THIS LINE
##----------------------------------------------------------------
##-----------------------------------------------------
##               CREATE DIRECTORIES
##-----------------------------------------------------
## Path to destination folder
outDirectory = "output"
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
####################################################################################
def prepCatch(catch,outDir,outgdb,n,method,outFile):
    print "Process step 1 : Preparing catchments shp"
    arcpy.CreateFileGDB_management(outDir, outgdb)
    arcpy.CopyFeatures_management(catch, outFile)
    ## Delete field
    fieldslist = arcpy.ListFields(outFile)
    Listfield  = []        
    for f in fieldslist:
        if not (str(f.name) == "OBJECTID" or str(f.name) =="Shape_Area" or str(f.name) =="Shape_Length" or str(f.name) =="Shape" or str(f.name) == "CATCHNUM"  ):
            Listfield.append(str(f.name))            
    arcpy.DeleteField_management(outFile, Listfield)
    return 
####################################################################################
def reclassConCriteria(inCatch,zoneField,criteriaList,criteriaName,floatingRaster,tempDir,n,method):
    print "Process step 2a : Reclass continuous criteria"
    for indicator in criteriaList:
        print " Reclassifying : " + indicator
        inFile = indicator
        if criteriaName[indicator] in floatingRaster:
            outRast = Int(Raster(indicator)*100)
            outRast.save(tempDir + "/" + criteriaName[indicator] + "_temp.tif")
            inFile = tempDir + "/" + criteriaName[indicator] + "_temp.tif"      
        ## Reclassify raster
        outReclass = Slice(inFile, n, method) 
        outReclass.save(tempDir + "/" + criteriaName[indicator] + ".tif")
        ## Tabulate indicator area class per catchment
        inRast = tempDir + "/" + criteriaName[indicator] + ".tif"
        outTable = tempDir + "/" + criteriaName[indicator].lower() + "_tabulatearea"
        TabulateArea(inCatch,zoneField, inRast,"VALUE",outTable,25)        
    return
#####################################################################################
def tabulateCatCriteria(inCatch,zoneField,criteriaList,criteriaName,outDir):
    print "Process step 3 : Reclass categorical criteria"
    for indicator in catIndicatorList:
        print " Reclassifying : " + indicator
        outTable = outDir + "/" + criteriaName[indicator].lower() + "_tabulatearea"
        TabulateArea(inCatch,zoneField, indicator,"VALUE",outTable,25)
    return
#####################################################################################
def genConCriteriaSHP(catch,joinField,criteriaList,criteriaName,tempDir,outDir,n,method):
    print "Process step 2b : Generate continuous criteria"
    for indicator in criteriaList:
        print " Generating : " +  indicator
        fm_name = arcpy.FieldMap()
        fms = arcpy.FieldMappings()
        fm_name.addInputField(catch, joinField)
        fms.addFieldMap(fm_name)
        fm_name = arcpy.FieldMap()
        for i in range(1,n+1):
            field = criteriaName[indicator] + str(i)
            arcpy.AddField_management(catch,field,"DOUBLE","14","0")
            fm_name.addInputField(catch, field)
            fms.addFieldMap(fm_name)
            fm_name = arcpy.FieldMap()
        ## Create a feature layer from the vegtype featureclass
        outTable = tempDir + "/" + criteriaName[indicator].lower() + "_tabulatearea"
        fieldList = arcpy.ListFields(outTable)
        layerName = criteriaName[indicator].lower()
        arcpy.MakeFeatureLayer_management(catch,layerName)
        arcpy.AddJoin_management(layerName, joinField, outTable, joinField)
        for i in range(1,n+1):
             if any("VALUE_" + str(i) in field.name for field in fieldList):
                env.workspace = tempOutputDir
                joinTable = criteriaName[indicator].lower() + "_tabulatearea"
                field = criteriaName[indicator] + str(i)
                calcExpression = "!" + joinTable + ":VALUE_" + str(i) + "!"
                ## Populate the newly created field with values from the joined table
                arcpy.CalculateField_management(layerName, field, calcExpression, "PYTHON")      
        ## Remove the join
        arcpy.RemoveJoin_management (layerName, joinTable)  
        ## Copy the layer to a new permanent feature class
        outName = criteriaName[indicator] + "_" + str(n) + "_" + method + ".shp"
        arcpy.FeatureClassToFeatureClass_conversion(layerName, outDir,outName,"",fms)
        arcpy.Delete_management(layerName)
#####################################################################################
def genCatCriteriaSHP(catch,joinField,criteriaList,criteriaName,tempDir,outDir):
    print "Process step 3 : Generate categorical criteria"
    for indicator in criteriaList:
        print " Generating : " + indicator
        fm_name = arcpy.FieldMap()
        fms = arcpy.FieldMappings()
        fm_name.addInputField(catch, joinField)
        fms.addFieldMap(fm_name)
        fm_name = arcpy.FieldMap()

        d = []
        rows = arcpy.SearchCursor(indicator,"","","VALUE","")
        for row in rows:
            val = row.getValue("VALUE")
            d.append(val)
        for i in d:
            field = criteriaName[indicator] + str(i)
            arcpy.AddField_management(catch,field,"DOUBLE","14","0")
            fm_name.addInputField(catch, field)
            fms.addFieldMap(fm_name)
            fm_name = arcpy.FieldMap()
        layerName =criteriaName[indicator].lower()
        arcpy.MakeFeatureLayer_management (catch,layerName)
        outTable= tempDir + "/" + criteriaName[indicator].lower() + "_tabulatearea"
        fieldList = arcpy.ListFields(outTable)
        arcpy.AddJoin_management (layerName, joinField, outTable, joinField)
        for i in d:
            if any("VALUE_" + str(i) in field.name for field in fieldList):
                env.workspace = tempDir
                joinTable = criteriaName[indicator].lower() + "_tabulatearea"
                field = criteriaName[indicator] + str(i)
                calcExpression = "!" + joinTable + ":VALUE_" + str(i) + "!"
                ## Populate the newly created field with values from the joined table
                arcpy.CalculateField_management(layerName, field, calcExpression, "PYTHON") 
        ## Remove the join
        arcpy.RemoveJoin_management(layerName, joinTable)  
        ## Copy the layer to a new permanent feature class
        outName = criteriaName[indicator] + ".shp"
        arcpy.FeatureClassToFeatureClass_conversion(layerName, outDir,outName,"",fms)
        arcpy.Delete_management(layerName)
    return
#####################################################################################
def genDBFCriteria(inCatch,outDir,joinField,n,method):
    print "Process step 4: genDBFCriteria"
    env.workspace = outDir
    layerName ="catchIndicators_" + str(n) + "_" + method
    fieldslist = arcpy.ListFields(inCatch)
    Listfield  = []        
    for f in fieldslist:
        if not (str(f.name) == "OBJECTID" or str(f.name) =="Shape_Area" or str(f.name) =="Shape_Length" or str(f.name) =="Shape" or str(f.name) == "CATCHNUM"):
            Listfield.append(str(f.name))            
    arcpy.DeleteField_management(inCatch, Listfield)
    arcpy.MakeTableView_management(inCatch,layerName)
    fcList = arcpy.ListFeatureClasses()
    for fc in fcList:
        fieldList =[]
        fieldnames = [f.name for f in arcpy.ListFields(fc)]
        for field in fieldnames:
            if field.startswith(fc[0:3]):
                fieldList.append(field)
        arcpy.MakeFeatureLayer_management(fc,fc[0:4])
        arcpy.JoinField_management(layerName, joinField, fc[0:4], joinField,fieldList)
        arcpy.Delete_management(fc[0:4])
    ## Create a fieldList that contain all the fieldnames 
    env.qualifiedFieldNames = False
    arcpy.TableToDBASE_conversion(layerName, outDir)
    return
#####################################################################################
arcpy.CheckOutExtension("Spatial")

##-------------------------------------------------
## STEP 1 : DATA PREPARATION
##-------------------------------------------------
## Copy catchments and delete attributes except CATCHNUM field
try:
    outCatch = tempOutputDir + "/" + indicatorsGDB + "/catchIndicators_" + str(n) + "_" + method
    prepCatch(catchments,tempOutputDir,indicatorsGDB,n,method,outCatch)

##-------------------------------------------------
## STEP 2 : PROCESS CONTINUOUS CRITERIA
##-------------------------------------------------
    ## Reclass continuous criteria
    reclassConCriteria(outCatch,catchID,conIndicatorList,conIndicatorName,floatRast,tempOutputDir,n,method)
    ## Generate dbf table for each continuous criteria
    genConCriteriaSHP(outCatch,catchID,conIndicatorList,conIndicatorName,tempOutputDir,FinalOutputDir,n,method)

##-------------------------------------------------
## STEP 3 : PROCESS CATEGORICAL CRITERIA
##-------------------------------------------------
    ## Reclass categorical criteria
    tabulateCatCriteria(outCatch,catchID,catIndicatorList,catIndicatorName,tempOutputDir)
    ## Generate dbf table for each categorical criteria
    genCatCriteriaSHP(outCatch,catchID,catIndicatorList,catIndicatorName,tempOutputDir,FinalOutputDir)

##-------------------------------------------------
## STEP 4 : ASSEMBLE CRITERIA TABLE
##-------------------------------------------------
    genDBFCriteria(outCatch,FinalOutputDir,catchID,n,method)
    
except:
    print "Failed to process...\n"
    print "Error message: "  + arcpy.GetMessage(0) + "\n"

print "The script ended with no error message"
sys.exit()

