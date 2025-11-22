bl_info = {
    "name": "Oimo's Batch FBX Exporter",
    "author": "Oimo & Gemini",
    "version": (2, 4), # (★ MODIFIED v2.4 - 余計な設定を全削除)
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar (N-key) > My Tool",
    "description": "Exports objects using pure default settings.",
    "category": "Import-Export",
}

import bpy
import os
import traceback
from datetime import datetime

# --- ログ機能 ---
def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def log_error(message, exception=None):
    log_message(message, "ERROR")
    if exception:
        print(traceback.format_exc())

# --- ルート検索 ---
def find_root_in_set(obj, object_set):
    current = obj
    while current.parent and current.parent in object_set:
        current = current.parent
    return current

# --- メインエクスポート処理 ---
def export_objects_logic(context, objects_to_export, base_path):
    
    # 子孫を選択する関数
    def select_hierarchy(obj):
        obj.select_set(True)
        for child in obj.children:
            select_hierarchy(child)

    log_message("="*60)
    log_message("BATCH EXPORT START (Minimal Settings)")
    
    if not base_path:
        return False, "Base Path を指定してください。"
    
    # 現在の選択状態を保存
    original_selection = list(context.selected_objects)
    original_active = context.view_layer.objects.active
    
    bpy.ops.object.select_all(action='DESELECT')
    
    exported_count = 0
    failed_exports = []

    for idx, obj in enumerate(objects_to_export, 1):
        asset_name = obj.name
        # フォルダ構成: BasePath / AssetName / AssetName.fbx
        target_folder = os.path.join(base_path, asset_name)
        export_path = os.path.join(target_folder, asset_name + ".fbx")
        
        log_message(f"Exporting {idx}/{len(objects_to_export)}: {asset_name}")
        
        try:
            os.makedirs(target_folder, exist_ok=True)
            
            # --- 選択処理 ---
            # 1. 親をアクティブにする (重要: FBXはアクティブオブジェクトを基準にすることがあるため)
            context.view_layer.objects.active = obj
            # 2. 階層ごと選択
            select_hierarchy(obj)
            
            # --- FBX書き出し ---
            # ★ 修正ポイント: パラメータを極限まで減らしました。
            # use_selection=True 以外はすべてBlenderのデフォルトに任せます。
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
            # 次のために選択解除
            bpy.ops.object.select_all(action='DESELECT')

    # --- 復元処理 ---
    for obj in original_selection:
        if obj.name in bpy.data.objects:
            obj.select_set(True)
    context.view_layer.objects.active = original_active
    
    log_message(f"Complete. Success: {exported_count}, Failed: {len(failed_exports)}")
    return True, f"完了: {exported_count} 件成功"

# --- オペレーター ---
class WM_OT_ExportCollection(bpy.types.Operator):
    bl_idname = "wm.export_collection"
    bl_label = "Export from Collection"

    def execute(self, context):
        props = context.scene.my_exporter_props
        base_path = props.base_path
        coll_name = props.collection_name

        if not base_path:
            self.report({'ERROR'}, "保存先パスを指定してください")
            return {'CANCELLED'}

        coll = bpy.data.collections.get(coll_name)
        if not coll:
            self.report({'ERROR'}, "コレクションが見つかりません")
            return {'CANCELLED'}
        
        # コレクション内のルートオブジェクトを探す
        objs = [o for o in coll.all_objects if o.type in {'MESH', 'EMPTY'}]
        obj_set = set(objs)
        roots = {find_root_in_set(o, obj_set) for o in objs}
        
        success, msg = export_objects_logic(context, list(roots), base_path)
        self.report({'INFO' if success else 'ERROR'}, msg)
        return {'FINISHED'}

class WM_OT_ExportSelected(bpy.types.Operator):
    bl_idname = "wm.export_selected"
    bl_label = "Export Selected"

    def execute(self, context):
        props = context.scene.my_exporter_props
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

# --- パネル ---
class VIEW3D_PT_MyExporterPanel(bpy.types.Panel):
    bl_label = "Batch FBX Exporter"
    bl_idname = "VIEW3D_PT_my_exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "My Tool"

    def draw(self, context):
        layout = self.layout
        props = context.scene.my_exporter_props
        
        layout.prop(props, "base_path")
        
        layout.separator()
        layout.label(text="Collection Export:")
        layout.prop_search(props, "collection_name", bpy.data, "collections", text="")
        layout.operator("wm.export_collection")
        
        layout.separator()
        layout.label(text="Selection Export:")
        layout.operator("wm.export_selected")

# --- 登録処理 ---
class MyExporterProperties(bpy.types.PropertyGroup):
    base_path: bpy.props.StringProperty(name="Export Path", subtype='DIR_PATH')
    collection_name: bpy.props.StringProperty(name="Collection")

classes = [
    MyExporterProperties,
    WM_OT_ExportCollection,
    WM_OT_ExportSelected,
    VIEW3D_PT_MyExporterPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.my_exporter_props = bpy.props.PointerProperty(type=MyExporterProperties)

def unregister():
    del bpy.types.Scene.my_exporter_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()