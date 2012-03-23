# ---------------------------------------------------------------------------
# ExportToOSM.py
# Created on: Wed Jul 01 2009
# Created by: John Reiser <reiser@rowan.edu>
#             http://users.rowan.edu/~reiser/osm/
# Modified on: Mon Jul 20 2009
#   - Added ability to add tags to all features
#   - Acknowledges "_" and "osm_" prefixed fields
# Modified on Tue Aug 18 2009
#   - Added ability to export by groups, reduces running time
# Usage: ExportToOSM.py <input feature class> <output osm file>
# License: Copyright (C) 2009, John Reiser
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
# ---------------------------------------------------------------------------

creator_id = u"ArcGIS Exporter" 
node_i = -1
way_i = -1
rel_i = -1

import arcgisscripting, os, sys, re
gp = arcgisscripting.create(9.3)

def XmlEncode(text):
    return str(text).replace("&", "&amp;").replace("\"", "&quot;")

if len(sys.argv)< 3:
    gp.AddError("Insufficient parameters.")
    sys.exit(2)

ifc = sys.argv[1]
osm = sys.argv[2]
tags = {}

des = gp.Describe(ifc)
oid = des.OIDFieldName
grpfield = [0]

if len(sys.argv) >= 4:
    if not (sys.argv[3] == "#"):
        for item in sys.argv[3].split(";"):
            pair = item.split("=")
            tags[pair[0].strip()] = pair[1].strip()
    if not (sys.argv[4] == "#"):
        grpfield = []
        result = gp.GetCount_management(ifc)
        cnt = int(result.GetOutput(0))
        cursor = gp.searchcursor(ifc)
        row = cursor.next()
        gp.SetProgressor("step", "Generating group identifiers...", 0, cnt, 1)
        while row:
            if(int(row.GetValue(sys.argv[4])) not in grpfield):
                grpfield.append(int(row.GetValue(sys.argv[4])))
            gp.SetProgressorPosition()
            row = cursor.next()
        gp.AddMessage(str(len(grpfield))+" groups in feature class.")

if not gp.Exists(ifc):
    gp.AddError("Input feature class not found.")
    sys.exit(2)

sr = des.SpatialReference

wgs84srs = gp.CreateObject("spatialreference")
wgs84srs.CreateFromFile(r"C:\Program Files\ArcGIS\Coordinate Systems\Geographic Coordinate Systems\World\WGS 1984.prj")

if not (sr.Type == "Geographic" and sr.Name == "GCS_WGS_1984"):
    gp.AddWarning("Input not WGS84 native.")
    # search cursor allows for a change in projection system
    # however, does not work with selected features within a layer
    # http://webhelp.esri.com/arcgisdesktop/9.3/index.cfm?TopicName=Setting_a_cursor%27s_spatial_reference

osmfile = open(osm, 'w')
xml  = u""
xml += u"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
xml += u"<osm version=\"0.6\" generator=\"" + creator_id + u"\">\n"
osmfile.write(xml)

if(des.ShapeType == "Polyline" or des.ShapeType == "Polygon"):
    gp.MakeFeatureLayer_management(ifc, "Input Feature", "", "", "")
    for group in grpfield:
        nodes = []
        ways = []
        relationships = []
        try:
            gp.AddMessage("Processing group "+str(group)+"...")
            if(group != 0):
                gp.SelectLayerByAttribute_management("Input Feature", "NEW_SELECTION", "\""+sys.argv[4]+"\" = "+str(group))
                rows = gp.SearchCursor(ifc, "\""+sys.argv[4]+"\" = "+str(group), wgs84srs)
            else:
                rows = gp.SearchCursor(ifc, "", wgs84srs)
            result = gp.GetCount_management("Input Feature")
            totalrows = int(result.GetOutput(0))
            rowcount = 0 
            gp.SetProgressor("step", "Processing feature " + str(rowcount) + " in group " + str(group), 0, totalrows, 1)

            row = rows.next()
            sfn = des.ShapeFieldName
            while row:        
                gp.SetProgressorLabel("Processing feature " + str(rowcount) + " in group " + str(group))
                gp.SetProgressorPosition(rowcount)
                partnum = 0
                feat = row.GetValue(sfn)
                partcount = feat.PartCount
                temprel = []
                while partnum < partcount:
                    inner = 0
                    tempway = {}
                    tempway['nodes'] = []
                    tempway['id'] = way_i

                    if feat.isMultipart:
                        temprel.append("o"+str(tempway['id']))
                        tempway['_type'] = 'multipolygon'
                        tempway['_role'] = 'outer'

                    pattern = re.compile('\w+')
                    for field in des.Fields:
                        fn = field.Name.lower()
                        if ((fn[:4] == "osm_") or (fn[0] == "_")):
                            if(pattern.match(str(row.GetValue(field.Name)))):
                                tempway[fn] = row.GetValue(field.Name)
                    way_i -= 1

                    points = feat.GetPart(partnum)
                    pnt = points.next()
                    while pnt:
                        if inner == 1:
                            if not "i"+str(tempway['id']) in temprel:
                                temprel.append("i"+str(tempway['id']))
                                tempway['_type'] = 'multipolygon'
                                tempway['_role'] = "inner"
                                way_i -= 1
                        existing_node = 0
                        for n in nodes:
                            if((round(float(pnt.y), 7) == n['lat']) and (round(float(pnt.x), 7) == n['lon'])):
                                existing_node = n['id']
                        if existing_node == 0:
                            tempnode = {}
                            tempnode['lat'] = round(float(pnt.y), 7)
                            tempnode['lon'] = round(float(pnt.x), 7)
                            tempnode['id'] = node_i
                            tempway['nodes'].append(node_i)
                            node_i -= 1
                            nodes.append(tempnode.copy())
                        else:
                            tempway['nodes'].append(existing_node)
                        pnt = points.next()
                        if not pnt:
                            ways.append(tempway.copy())
                            inner = 1
                            tempway['nodes'] = []
                            tempway['id'] = way_i
                            pnt = points.next()
                    partnum += 1
                if not len(temprel) == 0:
                    relationships.append(temprel)
                rowcount += 1
                row = rows.next()
            xml = u""
            for node in nodes:
                xml += u"  <node"
                if u"id" in node:
                    xml += u" id=\"" + str(node[u"id"]) + u"\""        
                if u"lat" in node:
                    xml += u" lat=\"" + str(node[u"lat"]) + u"\""        
                if u"lon" in node:
                    xml += u" lon=\"" + str(node[u"lon"]) + u"\""
                xml += u">\n"
                xml += u"    <tag k=\"created_by\" v=\"" + creator_id + u"\"/>\n"
                xml += u"  </node>\n"

            for way in ways:
                xml += u"  <way"
                if u"id" in way:
                    xml += u" id=\"" + str(way[u"id"]) + u"\""
                xml += u">\n"
                for node in way['nodes']:
                    xml += u"    <nd ref=\"" + str(node) + u"\"/>\n"
                for field in way:
                    if field[:4] == "osm_":
                        xml += u"    <tag k=\"" + str(field[4:]) + u"\" v=\"" + XmlEncode(way[field]) + u"\"/>\n"
                    if field[0] == "_":
                        xml += u"    <tag k=\"" + str(field[1:]) + u"\" v=\"" + XmlEncode(way[field]) + u"\"/>\n"
                for tag in tags:
                        xml += u"    <tag k=\"" + str(tag) + u"\" v=\"" + str(tags[tag]) + u"\"/>\n"
                xml += u"    <tag k=\"created_by\" v=\"" + creator_id + u"\"/>\n"    
                xml += u"  </way>\n"

            for rel in range(len(relationships)):
                if len(relationships[rel]) > 0:
                    xml += u"  <relation id=\"" + str(rel_i) + u"\">\n"
                    for member in relationships[rel]:
                        xml += u"      <member type=\"way\" ref=\"" + member[1:] + u"\" role=\""
                        if(member[0] == "o"):
                            xml += "outer"
                        else:
                            xml += "inner"
                        xml += "\" />\n"
                    xml += u'    <tag k="type" v="multipolygon"/>\n'
                    xml += u"    <tag k=\"created_by\" v=\"" + creator_id + u"\"/>\n"    
                    xml += u"  </relation>\n"
                rel_i = rel_i - 1 
            osmfile.write(xml)
        except Exception, ErrorDesc:
            gp.AddError(str(ErrorDesc))
            sys.exit(2)
#gp.SetProgressor("default", "Generating XML...")
#gp.AddMessage("Generating OSM XML...")
# <element attr="val">
xml = u"</osm>\n"
osmfile.write(xml)
osmfile.close()

gp.AddMessage("OSM XML saved to output file.")
