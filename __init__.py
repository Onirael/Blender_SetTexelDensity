bl_info = {
    "name": "Get/Set Texel Density",
    "author": "Onirael",
    "version": (1,0),
    "blender": (2, 80, 0),
    "description: DEBUG VERSION"
    "Category": "UV"
    }



import bpy, bmesh, math
import numpy as np
from mathutils import Vector

# 3D tri area ABC is half the length of AB cross product AC 
def tri_area( co1, co2, co3 ):
    return (co2 - co1).cross( co3 - co1 ).length / 2.0

def DeselectAll(bMesh):
    for p in bMesh.faces:
        p.select = False

def ResetSelection(context):
    obj = context.object
    bEditMode = obj.mode == 'EDIT'
    if bEditMode:
        bpy.ops.object.mode_set()
        bpy.ops.object.mode_set(mode='EDIT')

def GetIslands(bMesh, bExpandSelection=True):
    selectedFaces = [p.index for p in bMesh.faces if p.select]

    bMesh.faces.ensure_lookup_table()

    uvIslands = []
    for faceIndex in selectedFaces:
        DeselectAll(bMesh)
        bMesh.faces[faceIndex].select = True
        if bExpandSelection:
            bpy.ops.mesh.select_linked(delimit={'UV'})
        newFaces = np.asarray([p.index for p in bMesh.faces if p.select])
    
        bIsContained = False
        for island in uvIslands:
            bIsContained = newFaces[0] == island[0]
            if bIsContained:
                break
        if not bIsContained:
            uvIslands.append(newFaces)
          
    return uvIslands

def GetFaceDensities(bMesh, uvIslands, texResolution):
    triangle_loops = bMesh.calc_loop_triangles()
    uv_loop = bMesh.loops.layers.uv[0]
    
    DeselectAll(bMesh)

    areas = {}
    densities = {}
    for island in uvIslands:
        areas.update({bMesh.faces[face].index: (0.0, 0.0) for face in island})
        densities.update({bMesh.faces[face].index: 0.0 for face in island})

    for loop in triangle_loops:
        face = loop[0].face.index
        try: # Check if key exists
            uv_area, face_area = areas[face]
        except KeyError:
            continue
    
        face_area += tri_area(*(l.vert.co for l in loop))
        uv_area += tri_area(*(Vector((*l[uv_loop].uv, 0)) for l in loop))
        if areas[face] != (0.0, 0.0):
            densities[face] = texResolution * math.sqrt(uv_area/(face_area*10000))
        areas[face] = (uv_area, face_area)
    return densities

def ScaleUV(context, bMesh, targetDensity, uvIslands, densities):
    startContext = context.area.ui_type
    context.area.ui_type = 'UV'

    for island in uvIslands:
        islandDensities = np.zeros(island.shape)
        i=0
        for face in island:
            islandDensities[i] = densities[face]
            i+=1
            bMesh.faces[face].select = True
        islandDensity = np.mean(islandDensities)
    
        scale = targetDensity/islandDensity
        bpy.ops.transform.resize(value=(scale, scale, scale),
                                 mirror=True,
                                 use_proportional_edit=False,
                                 proportional_edit_falloff='SMOOTH',
                                 proportional_size=1,
                                 use_proportional_connected=False,
                                 use_proportional_projected=False)
    context.area.ui_type = startContext

def GetDensity(context, texResolution, bExpandSelection=True):
    obj = context.object
    ResetSelection(context)
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    
    bContinue = False
    for face in bm.faces:
        if face.select:
            bContinue = True
            break
        
    if bContinue:
        uvIslands = GetIslands(bm, bExpandSelection)
        densities = GetFaceDensities(bm, uvIslands, texResolution)
    
        # Select islands and get per-island density
        perIslandDensities = np.zeros((len(uvIslands)))
        i=0
        for island in uvIslands:
            islandDensities = np.zeros(island.shape)
            n=0
            for face in island:
                islandDensities[n] = densities[face]
                bm.faces[face].select = True
                n+=1
            perIslandDensities[i] = np.mean(islandDensities)
            i+=1
            

        bmesh.update_edit_mesh(obj.data)
        bm.free()
        
        # Return average of all face densities
        return np.mean(perIslandDensities)
    else:
        bm.free()
        print("No face was selected")
        return 0

def SetDensity(context, targetDensity, texResolution):
    obj = context.object
    ResetSelection(context)
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    uvIslands = GetIslands(bm)
    densities = GetFaceDensities(bm, uvIslands, texResolution)
    ScaleUV(context, bm, targetDensity, uvIslands, densities)
    
    bmesh.update_edit_mesh(obj.data)
    bm.free()







#-------------------- Widgets -----------------------#

class SceneProps(bpy.types.PropertyGroup):
    density: bpy.props.FloatProperty(name="Texel Density",
                                   default=5.12,
                                   min=0.0,
                                   precision=2,
                                   description="Value in texels/cm")
    texRes: bpy.props.IntProperty(name="Texture Resolution",
                                  default=1024,
                                  min=1,
                                  description="Value in pixels")
    expandSelection: bpy.props.BoolProperty(name="Expand Selection",
                                            default=True,
                                            description="Whether the 'Get' selection should be expanded to UV islands")
    
class GetButton(bpy.types.Operator):
    """Gets the texel density of selected faces"""
    bl_idname = "uv.get_button"
    bl_label = "Get"
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        texRes = context.scene.SceneProps.texRes
        bExpandSelection = context.scene.SceneProps.expandSelection
        newDensity = GetDensity(context, texRes, bExpandSelection)
        context.scene.SceneProps.density = newDensity
        return {'FINISHED'}
    
class SetButton(bpy.types.Operator):
    """Sets the texel density of the UV islands containing the selected faces"""
    bl_idname = "uv.set_button"
    bl_label = "Set"

    def execute(self, context):
        targetDensity = context.scene.SceneProps.density
        texRes = context.scene.SceneProps.texRes
        SetDensity(context, targetDensity, texRes)
        return {'FINISHED'}

class MainWidget(bpy.types.Panel):
    """Gets or sets the texel density of UV islands"""
    #bl_idname = "uv.texel_density"
    bl_idname = "UV_PT_texel_density"
    bl_label = "Get/Set Texel Density"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Tools"
    #bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        row0 = self.layout.row(align=True)
        items = context.scene.SceneProps
        row0.prop(items, "texRes")
        row0.prop(items, "density")
        
        row1 = self.layout.row(align=True)
        row1.operator(GetButton.bl_idname)
        row1.operator(SetButton.bl_idname)
        self.layout.prop(items, "expandSelection")
        
    @classmethod
    def poll(self,context):
        return True
        
    def execute(self, context):
        return {'FINISHED'}
    
    
    
#---------------------- Implementation -------------------#

def menu_func(self, context):
    self.layout.operator(MainWidget.bl_idname)
    
classes = (SceneProps,
           GetButton,
           SetButton,
           MainWidget)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.IMAGE_MT_uvs.append(menu_func)
    bpy.types.Scene.SceneProps = bpy.props.PointerProperty(type=SceneProps)

def unregister():    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del(bpy.types.Scene.SceneProps)
    bpy.types.IMAGE_MT_uvs.remove(menu_func)