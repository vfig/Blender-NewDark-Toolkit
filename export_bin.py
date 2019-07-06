# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Script copyright (C) Tom N Harris
# Contributors: Campbell Barton, Bob Holcomb, Richard Lärkäng, Damien McGinnes, Mark Stijnman
# 2.80 Update by Robin Collier

######################################################

import bpy
import os
import shutil

if os.name == 'nt':
    convert_exe = '""' + os.path.split(__file__)[0] + os.path.sep + \
                  'convert.exe" -depth 8 -type palette "{}" "{}""'
else:
    convert_exe = 'convert -depth 8 -type palette "{}" "{}"'


######################################################
# EXPORT
######################################################

#2.80 added this def:
def get_diffuse_texture(material):
    mNodes = material.node_tree.nodes

    #get the material output node which all materials should have
    matOutputNode = mNodes.get("Material Output")

    #get whatever shader is the surface input to the material node - likely to be Diffuse BSDF or Principled BSDF
    shaderNode = matOutputNode.inputs[0].links[0].from_node

    #get the image texture that links to the shader node
    try:
        inputNode = shaderNode.inputs[0].links[0].from_node
        return inputNode.image.name

    except:
        return None

def get_material_colour(material):
    mNodes = material.node_tree.nodes

    #get the material output node which all materials should have
    matOutputNode = mNodes.get("Material Output")

    #get whatever shader is the surface input to the material node - likely to be Diffuse BSDF or Principled BSDF
    shaderNode = matOutputNode.inputs[0].links[0].from_node
    
    #get the colour
    c = shaderNode.inputs[0].default_value
    return((c[0], c[1], c[2]))

def make_material_str(i, material, image, operator):
    '''Make a material chunk out of a blender material.'''

    material= bpy.data.materials[material.name] #get all custom property values up to date
    mat_str = [str(i)]
    mat_str.append('"' + (material.name if material else "") + '"')
    
    if not material:
        mat_str.append("FLAT")
        mat_str.append("RGB 204,204,204")
        mat_str.append("TRANSP 0")

    else:
        #2.80 material.use_shadeless no longer exists. Using custom property instead
        shaderValue = str(material.get("SHADER"))
        if shaderValue == "PHONG":
            shaderType = "PHONG"
        else:
            shaderType = "FLAT"
        
        mat_str.append(shaderType)
        
        mCol = get_material_colour(material)

        rgb_str = "RGB "+",".join([str(int(c * 255)) for c in mCol])

        #2.80 material.texture_slots no longer exists
        texture = get_diffuse_texture(material)
        if texture:
            mat_str.append('TMAP "' + texture + '",0')

        else:
            mat_str.append(rgb_str)
        
        #2.80 material.emit does not exist, neither does material.use_transparency
        #custom properties required instead
        illum = material.get("ILLUM")
        if illum:
            mat_str.append("ILLUM "+ str(check0to100("TRANSP", transp, material, operator)))

        transp = material.get("TRANSP")
        if transp:
            mat_str.append("TRANSP "+ str(check0to100("TRANSP", transp, material, operator)))
        else:
            mat_str.append("TRANSP 0")

    return ",".join(mat_str) + ";\n"

#Checks if value (of custom property) is a number and between 0 and 100
#If < 0, returns 0, if > 100, returns 100
def check0to100(propName, value, material, operator):
    withinLimits = False
    try:    
        valInt = int(value)
        if valInt > 0 and valInt <= 100:
            withinLimits = True
            result = valInt
        elif valInt < 0:
            result = 0
        elif valInt > 100:
            result = 100
    except:
        return 0
        
    if withinLimits == False:
        eMsg = propName + " must be between 0 and 100 for material \"" + material.name + "\". Using \"" + str(result) + "\" as value."
        operator.report({'WARNING'}, eMsg)
        print(eMsg)

    return result

def make_vertex_str(vertex):
    #return ",".join([format(co, ".6f") for co in vertex.co]) + ";\n"
    return ",".join(str(round(co, 6)) for co in vertex.co) + ";\n"
    #return ",".join(str(co) for co in vertex.co) + ";\n"

def make_face_str(num, face, uv_tex, vert_map, materials, materialDict):
    if face.material_index < len(materials):
        mat = materials[face.material_index]
        mat_name = mat.name if mat is not None else None
        img_name = get_diffuse_texture(mat)
        mat_key = (mat_name, img_name)
        mat_index = 0 if mat_key not in materialDict else materialDict[mat_key][0]
    else:
        mat_index = 0
    #point = "(" + ",".join([str(round(co, 6)) for co in face.vertices]) + ")"    
    point = "(" + ",".join([str(co) for co in face.vertices]) + ")"    
    
    return "0,N,{},{:>4x},{};\n".format(num, mat_index, point)


#from obj exporter
def mesh_triangulate(me):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    #bmesh.ops.split_edges(bm, edges=bm.edges)  
    bm.to_mesh(me)
    bm.free()


class EmptyUV:
    uv = (0.0, 0.0)
    def __getitem__(self, index): return self

def padTo6(uv):
    u = "{:.6f}".format(uv[0])
    v = "{:.6f}".format(uv[1])
    return "(" + u + "," + v + ")"

def generateUVs(me):
    uv_act = me.uv_layers.active
    uv_layer = uv_act.data if uv_act is not None else EmptyUV()
    verts = me.vertices
    loop_vert = {l.index: l.vertex_index for l in me.loops}
    
    lines = [] #lines to be written to .e file
    i = 0 #face counter
    textureCount = 0 #if mesh has a mixture of textures and RGBs, RGB faces will have UVs of (-1,-1)
    for face in me.polygons:
        face_material = bpy.data.materials[me.materials[face.material_index].name]
        texture = get_diffuse_texture(face_material)
        if texture:
            textureCount = textureCount + 1
            line = str(i) + ","
            v = 0 #vertex counter
            for li in face.loop_indices:
                uv = uv_layer[li].uv
                coords = padTo6(uv)
                if v < 2:
                    coords = coords + ","
                else:
                    coords = coords + ";"
                    v = 0
                v = v + 1
                line = line + coords
            lines.append(line)
        else:
            lines.append(dummyUV(i))
        i = i+1
    
    if textureCount == 0:
        lines=[] #don't return dummy UV coords if all faces are RGB
    return lines

#if a face has no texture, return dummy UV coords
def dummyUV(faceID):
    uv = ",(-1.000000, -1.000000)"
    return str(faceID) + uv + uv + uv + ";"

def convert_to_bin(efile, binfile, bsp_dir, opt, ep, centre, bin_copy, game_dir, autodel):
    bsp = os.path.join(bsp_dir, "BSP")
    centString = ""
    if centre:
        centString = " -o"
    command = "\"" + bsp + "\" \"" + efile + "\" \"" + binfile + "\" -ep" + str(ep) + " -l" + str(opt) + " -V" + centString
    print("Converting to .bin...")
    print(command)
    os.system('call ' + command)
    if bin_copy:
        obj_dir = os.path.join(game_dir, "obj")
        if not os.path.exists(obj_dir):
            os.makedirs(obj_dir)
        try:
            shutil.copy(binfile, obj_dir)
            print(os.path.basename(binfile) + " file copied to obj folder of Thief game.")
            if autodel:
                os.remove(efile)
                os.remove(binfile)
                print("Temporary files deleted.")
            return 1
        except:
            print("\nERROR! I guess BIN file wasn't generated!")
            return 0
        
def copy_textures(materialDict, copyType, game_dir):
    if copyType > 0:
        txt16 = os.path.join(game_dir, "obj", "txt16")
        for m in materialDict.keys():
            tex = get_diffuse_texture(bpy.data.materials[m[0]])
            if tex is not None:
                img = bpy.data.images[tex]
                src_path = img.filepath
                allowCopy = True
                if copyType == 1: #only allow copying if dest does not exist
                    dest_file = os.path.join(txt16, os.path.basename(src_path))
                    if os.path.isfile(dest_file):
                        print(os.path.join(txt16, os.path.basename(src_path)) + " already exists.")
                        allowCopy = False
                if allowCopy:
                    if not os.path.exists(txt16):
                        os.makedirs(txt16)
                    print("copying " + src_path + " to " + txt16)
                    shutil.copy(src_path, txt16)

def save(operator,
         context, filepath="",
         use_selection=True,
         apply_modifiers=True,
         global_matrix=None,
         bsp_dir="",
         game_dir_ID = 1,
         game_dir1="", game_dir2="", game_dir3="", game_dir4="", game_dir5="",
         bsp_optimization=0, ep=0.0, centering=True, bin_copy=True, autodel=False,
         tex_copy="1"
         ):

    import mathutils

    import time

    '''Save the Blender scene to a E file.'''

    # Time the export
    time1 = time.clock()
#	Blender.Window.WaitCursor(1)

    # Open the file for writing:
    efile = filepath.replace(".bin", ".e")
    file = open(efile, 'w', encoding='ascii')

    file.write("""COMMENT{{
//	Exported by Blender {0} from {1}
}}

""".format(bpy.app.version_string, bpy.path.display_name(bpy.data.filepath)))

    if global_matrix is None:
        global_matrix = mathutils.Matrix()

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')

    # Make a list of all materials used in the selected meshes (use a dictionary,
    # each material is added once):
    materialDict = {}
    mesh_objects = []

    scene = context.scene
    depsgraph = context.evaluated_depsgraph_get()

    if use_selection:
        objects = (ob for ob in scene.objects if ob.visible_get() and ob.select_get())
    else:
        objects = (ob for ob in scene.objects if ob.visible_get())

    for ob in objects:
        ob_for_convert = ob.evaluated_get(depsgraph) if apply_modifiers else ob.original

        if ob.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
            continue

        try:
            data = ob_for_convert.to_mesh()
            mesh_triangulate(data)
        except:
            data = None
        
        mat = ob.matrix_world
        
        if data:
            data.transform(global_matrix @ mat)
            mesh_objects.append((ob_for_convert, data))
            mat_ls = data.materials
            mat_ls_len = len(mat_ls)
            
            if mat_ls_len:
                for p in data.polygons:
                    material = data.materials[p.material_index]
                    mName = material.name
                    texName = get_diffuse_texture(material)
                    if texName is not None:
                        texImage = bpy.data.images[texName]
                    else:
                        texImage = None
                    
                    materialDict.setdefault((mName, texName), (len(materialDict)+1, material, texImage))
            else:
                eMsg = "\"" + ob.name + "\" has no materials."
                print(eMsg)
                operator.report({'ERROR'}, ob.name + " has no materials.")
                return{'CANCELLED'}
    
    # Make material chunks for all materials used in the meshes:
    file.write("MATERIALS{\n")
    for num, mat, image in materialDict.values():
        file.write(make_material_str(num, mat, image, operator))
    file.write("}\n\n")

    # Create object chunks for all meshes:
    for ob, blender_mesh in mesh_objects:

        # set the object name
        file.write('BEGIN "'+ob.name+'"\n\n')

        vert_map = {}

        file.write("POINTS{\n")
        for i, vert in enumerate(blender_mesh.vertices):
            vert_map[vert.index] = i
            file.write(make_vertex_str(vert))
        file.write("}\n\n")

        #if len(data.uv_layers): #original way
        if len(blender_mesh.polygons):
            file.write("PARTS{\n")
            for i, f, uf in zip(range(len(blender_mesh.polygons)), blender_mesh.polygons, blender_mesh.uv_layers.active.data):
                file.write(make_face_str(i, f, uf, vert_map, blender_mesh.materials, materialDict))
            
            file.write("}\n\n")

            #generate UV coords for each face
            uvCoords = generateUVs(blender_mesh)
            if uvCoords:
                file.write("PART_MAPPINGS{\n")
                for uv in uvCoords:
                    file.write(uv + "\n")
                file.write("}\n\n")

    file.write("END\n")

    # Close the file:
    file.close()
    
    dirs = [game_dir1, game_dir2, game_dir3, game_dir4, game_dir5]
    game_dir = dirs[game_dir_ID -1]

    result = convert_to_bin(efile, filepath, bsp_dir, bsp_optimization, ep, centering, bin_copy, game_dir, autodel)
    if result == 1:
        copy_textures(materialDict, int(tex_copy), game_dir)
        print("Export & Conversion time: %.2f" % (time.clock() - time1))
        operator.report({'INFO'}, 'Done')
    else:
        operator.report({'ERROR'}, 'Error writing BIN file!')

    return {'FINISHED'}