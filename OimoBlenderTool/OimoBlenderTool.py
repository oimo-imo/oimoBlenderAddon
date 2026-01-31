bl_info = {
    "name": "OimoBlenderTool",
    "author": "Oimo",
    "version": (2, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > OimoTool",
    "description": "便利なショートカットとツールをまとめたアドオン (Rename & Batch Exporter 統合版)",
    "category": "3D View",
}

import bpy
import bmesh
import os
import traceback
from datetime import datetime

# ========================================================================
#   COMMON UTILS
# ========================================================================

def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def log_error(message, exception=None):
    log_message(message, "ERROR")
    if exception:
        print(traceback.format_exc())

# ========================================================================
#   FEATURE 1: CORE TOOLS (Drop to Floor, Set Origin, Reset Cursor)
# ========================================================================

class OBJECT_OT_OimoDropToFloor(bpy.types.Operator):
    """選択したオブジェクトの位置(XY)は変えずに、底面を地面(Z=0)に合わせます"""
    bl_idname = "object.oimo_drop_to_floor"
    bl_label = "床に接地 (Drop to Floor)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                context.view_layer.update()
                world_corners = [obj.matrix_world @ list(corner) for corner in obj.bound_box]
                min_z = min([co.z for co in world_corners])
                obj.location.z -= min_z

        self.report({'INFO'}, "オブジェクトを接地しました")
        return {'FINISHED'}


class OBJECT_OT_OimoSetOriginToSelected(bpy.types.Operator):
    """編集モードでの選択位置(頂点・辺・面)に原点を移動"""
    bl_idname = "object.oimo_set_origin_selected"
    bl_label = "選択位置へ原点移動"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, "編集モードで実行してください")
            return {'CANCELLED'}

        bpy.ops.view3d.snap_cursor_to_selected()
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        bpy.ops.object.mode_set(mode='EDIT')
        
        self.report({'INFO'}, "原点を移動しました")
        return {'FINISHED'}


class VIEW3D_OT_OimoResetCursor(bpy.types.Operator):
    """3Dカーソルをワールド原点(0,0,0)に戻します"""
    bl_idname = "view3d.oimo_reset_cursor"
    bl_label = "カーソルを原点へリセット"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.cursor.location = (0.0, 0.0, 0.0)
        context.scene.cursor.rotation_euler = (0.0, 0.0, 0.0)
        self.report({'INFO'}, "3Dカーソルをリセットしました")
        return {'FINISHED'}



class VIEW3D_OT_OimoViewSelected(bpy.types.Operator):
    """選択したオブジェクトをフレームインします (NumPad .)"""
    bl_idname = "view3d.oimo_view_selected"
    bl_label = "選択をフレームイン"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.view3d.view_selected()
        return {'FINISHED'}


# ========================================================================
#   FEATURE 2: RENAME & MATERIAL APPLIER
# ========================================================================

class OBJECT_OT_OimoRenameAndMaterialApply(bpy.types.Operator):
    """選択オブジェクトに名前とマテリアルを適用します"""
    bl_idname = "object.oimo_rename_and_material_apply"
    bl_label = "名前とマテリアルを適用"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        obj_name_base = scene.oimo_tool_object_name
        mat_name = scene.oimo_tool_material_name
        selected_objects = context.selected_objects

        # --- ① 入力チェック ---
        if not selected_objects:
            self.report({'WARNING'}, "オブジェクトが選択されていません。")
            return {'CANCELLED'}

        if not obj_name_base and not mat_name:
            self.report({'WARNING'}, "オブジェクト名またはマテリアル名を入力してください。")
            return {'CANCELLED'}

        # --- ② マテリアル処理 ---
        material_to_apply = None
        if mat_name:
            material_to_apply = bpy.data.materials.get(mat_name)
            if not material_to_apply:
                material_to_apply = bpy.data.materials.new(name=mat_name)
                self.report({'INFO'}, f"マテリアル '{mat_name}' を新規作成しました。")

            for obj in selected_objects:
                if obj.type == 'MESH':
                    if obj.data.materials:
                        obj.data.materials[0] = material_to_apply
                    else:
                        obj.data.materials.append(material_to_apply)

        # --- ③ リネーム処理 ---
        if obj_name_base:
            top_level_parents = [obj for obj in selected_objects if obj.parent is None or obj.parent not in selected_objects]
            
            if not top_level_parents:
                self.report({'WARNING'}, "リネーム対象の親オブジェクトが見つかりません。")
            else:
                top_level_parents.sort(key=lambda o: o.name)
                is_multiple_parents = len(top_level_parents) > 1
                
                for i, parent in enumerate(top_level_parents):
                    base_name = f"{obj_name_base}.{i+1:03d}" if is_multiple_parents else obj_name_base
                    parent.name = base_name
                    
                    all_descendants = list(parent.children_recursive)
                    selected_descendants = [obj for obj in selected_objects if obj in all_descendants]
                    selected_descendants.sort(key=lambda o: o.name)
                    
                    for j, child in enumerate(selected_descendants):
                        child.name = f"{base_name}.{j+1:03d}"

        self.report({'INFO'}, "処理が完了しました。")
        return {'FINISHED'}


# ========================================================================
#   FEATURE 3: BATCH FBX EXPORTER
# ========================================================================

def find_root_in_set(obj, object_set):
    current = obj
    while current.parent and current.parent in object_set:
        current = current.parent
    return current

def export_objects_logic(context, objects_to_export, base_path):
    def select_hierarchy(obj):
        obj.select_set(True)
        for child in obj.children:
            select_hierarchy(child)

    log_message("="*60)
    log_message("BATCH EXPORT START (OimoBlenderTool)")
    
    if not base_path:
        return False, "Base Path を指定してください。"
    
    original_selection = list(context.selected_objects)
    original_active = context.view_layer.objects.active
    
    bpy.ops.object.select_all(action='DESELECT')
    
    exported_count = 0
    failed_exports = []

    for idx, obj in enumerate(objects_to_export, 1):
        asset_name = obj.name
        target_folder = os.path.join(base_path, asset_name)
        export_path = os.path.join(target_folder, asset_name + ".fbx")
        
        log_message(f"Exporting {idx}/{len(objects_to_export)}: {asset_name}")
        
        try:
            os.makedirs(target_folder, exist_ok=True)
            context.view_layer.objects.active = obj
            select_hierarchy(obj)
            
            bpy.ops.export_scene.fbx(
                filepath=export_path,
                use_selection=True
            )
            
            if os.path.exists(export_path):
                exported_count += 1
            else:
                raise Exception("File not created")
                
        except Exception as e:
            log_error(f"Failed: {asset_name}", e)
            failed_exports.append(asset_name)
            
        finally:
            bpy.ops.object.select_all(action='DESELECT')

    for obj in original_selection:
        if obj.name in bpy.data.objects:
            obj.select_set(True)
    if original_active and original_active.name in bpy.data.objects:
        context.view_layer.objects.active = original_active
    
    log_message(f"Complete. Success: {exported_count}, Failed: {len(failed_exports)}")
    return True, f"完了: {exported_count} 件成功"


class WM_OT_OimoExportCollection(bpy.types.Operator):
    bl_idname = "wm.oimo_export_collection"
    bl_label = "Export from Collection"

    def execute(self, context):
        props = context.scene.oimo_exporter_props
        base_path = props.base_path
        coll_name = props.collection_name

        if not base_path:
            self.report({'ERROR'}, "保存先パスを指定してください")
            return {'CANCELLED'}

        coll = bpy.data.collections.get(coll_name)
        if not coll:
            self.report({'ERROR'}, "コレクションが見つかりません")
            return {'CANCELLED'}
        
        objs = [o for o in coll.all_objects if o.type in {'MESH', 'EMPTY'}]
        obj_set = set(objs)
        roots = {find_root_in_set(o, obj_set) for o in objs}
        
        success, msg = export_objects_logic(context, list(roots), base_path)
        self.report({'INFO' if success else 'ERROR'}, msg)
        return {'FINISHED'}


class WM_OT_OimoExportSelected(bpy.types.Operator):
    bl_idname = "wm.oimo_export_selected"
    bl_label = "Export Selected"

    def execute(self, context):
        props = context.scene.oimo_exporter_props
        base_path = props.base_path

        if not base_path:
            self.report({'ERROR'}, "保存先パスを指定してください")
            return {'CANCELLED'}

        objs = [o for o in context.selected_objects if o.type in {'MESH', 'EMPTY'}]
        if not objs:
            self.report({'WARNING'}, "メッシュまたはエンプティを選択してください")
            return {'CANCELLED'}
            
        obj_set = set(objs)
        roots = {find_root_in_set(o, obj_set) for o in objs}
        
        success, msg = export_objects_logic(context, list(roots), base_path)
        self.report({'INFO' if success else 'ERROR'}, msg)
        return {'FINISHED'}


# ========================================================================
#   GUI PANELS
# ========================================================================

class VIEW3D_PT_OimoPanel(bpy.types.Panel):
    """メインツールパネル"""
    bl_label = "Oimo Tools"
    bl_idname = "VIEW3D_PT_oimo_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Oimo Tool"

    def draw(self, context):
        layout = self.layout
        
        # --- 整列 ---
        layout.label(text="整列ツール", icon='ALIGN_BOTTOM')
        row = layout.row()
        row.scale_y = 1.5
        row.operator(OBJECT_OT_OimoDropToFloor.bl_idname, text="床に接地 (Z=0)")

        layout.separator()

        # --- 原点・カーソル ---
        layout.label(text="原点・カーソル", icon='PIVOT_CURSOR')
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator(OBJECT_OT_OimoSetOriginToSelected.bl_idname, text="選択位置へ原点移動")
        
        row = layout.row()
        row.scale_y = 1.2
        row.operator(VIEW3D_OT_OimoResetCursor.bl_idname, text="3Dカーソルリセット", icon='CURSOR')

        row = layout.row()
        row.scale_y = 1.2
        row.operator(VIEW3D_OT_OimoViewSelected.bl_idname, text="選択をフレームイン", icon='ZOOM_SELECTED')


class VIEW3D_PT_OimoRenamePanel(bpy.types.Panel):
    """リネーム＆マテリアルパネル"""
    bl_label = "Rename & Material"
    bl_idname = "VIEW3D_PT_oimo_rename_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Oimo Tool"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        box = layout.box()
        box.label(text="一括設定", icon='SETTINGS')
        
        col = box.column(align=True)
        col.prop(scene, "oimo_tool_object_name")
        col.prop(scene, "oimo_tool_material_name")
        
        layout.separator()
        layout.operator(OBJECT_OT_OimoRenameAndMaterialApply.bl_idname, icon='PLAY')


class VIEW3D_PT_OimoExporterPanel(bpy.types.Panel):
    """FBXエクスポートパネル"""
    bl_label = "Batch FBX Exporter"
    bl_idname = "VIEW3D_PT_oimo_exporter_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Oimo Tool"

    def draw(self, context):
        layout = self.layout
        props = context.scene.oimo_exporter_props
        
        layout.prop(props, "base_path")
        
        layout.separator()
        layout.label(text="Collection Export:")
        layout.prop_search(props, "collection_name", bpy.data, "collections", text="")
        layout.operator(WM_OT_OimoExportCollection.bl_idname)
        
        layout.separator()
        layout.label(text="Selection Export:")
        layout.operator(WM_OT_OimoExportSelected.bl_idname)


# ========================================================================
#   REGISTRATION
# ========================================================================

class OimoExporterProperties(bpy.types.PropertyGroup):
    base_path: bpy.props.StringProperty(name="Export Path", subtype='DIR_PATH')
    collection_name: bpy.props.StringProperty(name="Collection")

classes = (
    # Core
    OBJECT_OT_OimoDropToFloor,
    OBJECT_OT_OimoSetOriginToSelected,
    VIEW3D_OT_OimoResetCursor,
    VIEW3D_OT_OimoViewSelected,
    VIEW3D_PT_OimoPanel,
    # Rename
    OBJECT_OT_OimoRenameAndMaterialApply,
    VIEW3D_PT_OimoRenamePanel,
    # Exporter
    OimoExporterProperties,
    WM_OT_OimoExportCollection,
    WM_OT_OimoExportSelected,
    VIEW3D_PT_OimoExporterPanel,
)

def register_properties():
    # Rename Props
    bpy.types.Scene.oimo_tool_object_name = bpy.props.StringProperty(
        name="オブジェクト名",
        description="設定するオブジェクトのベース名",
        default="MyObject"
    )
    bpy.types.Scene.oimo_tool_material_name = bpy.props.StringProperty(
        name="マテリアル名",
        description="設定・作成するマテリアル名",
        default="MyMaterial"
    )
    # Exporter Props
    bpy.types.Scene.oimo_exporter_props = bpy.props.PointerProperty(type=OimoExporterProperties)

def unregister_properties():
    if hasattr(bpy.types.Scene, "oimo_tool_object_name"):
        del bpy.types.Scene.oimo_tool_object_name
    if hasattr(bpy.types.Scene, "oimo_tool_material_name"):
        del bpy.types.Scene.oimo_tool_material_name
    if hasattr(bpy.types.Scene, "oimo_exporter_props"):
        del bpy.types.Scene.oimo_exporter_props

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_properties()

def unregister():
    unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()