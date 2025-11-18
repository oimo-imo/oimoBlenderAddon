bl_info = {
    "name": "Oimo's Batch FBX Exporter",
    "author": "Oimo & Gemini",
    "version": (1, 3), # (★ MODIFIED v1.3 - デバッグ強化版)
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N-key) > My Tool",
    "description": "Exports objects (with hierarchy) to individual FBX files.",
    "category": "Import-Export",
}

import bpy
import os
import traceback

# --- (★ NEW) 階層の「ルート」を見つけるためのヘルパー関数 ---
def find_root_in_set(obj, object_set):
    """
    指定されたオブジェクトセット(object_set)の中で、
    obj の最上位の親を見つける。
    もし親がセットにいなければ、obj 自身がルート。
    """
    current = obj
    while current.parent and current.parent in object_set:
        current = current.parent
    return current

# --- 4. 共通のエクスポート処理 (メインロジック) ---
def export_objects_logic(context, objects_to_export, base_path):
    
    def select_descendants(parent_obj):
        """
        指定されたオブジェクトのすべての子孫を再帰的にたどり、
        MESHとEMPTYのみを選択状態にする
        """
        for child in parent_obj.children:
            select_descendants(child)
            if child.type in {'MESH', 'EMPTY'}:
                child.select_set(True)

    def deselect_descendants(parent_obj):
        """
        指定されたオブジェクトのすべての子孫を再帰的にたどり、
        MESHとEMPTYのみを選択解除する
        """
        for child in parent_obj.children:
            deselect_descendants(child)
            if child.type in {'MESH', 'EMPTY'}:
                child.select_set(False)
    
    if not base_path:
        print("ERROR: Base Path is not set.")
        return False, "Base Path を指定してください。"
    
    # パスの検証
    if not os.path.isabs(base_path):
        print(f"ERROR: Base Path is not absolute: {base_path}")
        return False, "Base Path は絶対パスで指定してください。"

    original_selection = context.selected_objects
    original_active = context.view_layer.objects.active
    
    bpy.ops.object.select_all(action='DESELECT')
    
    exported_count = 0
    failed_exports = []

    print(f"\n=== Starting export to: {base_path} ===")
    print(f"Objects to export: {len(objects_to_export)}")
    
    for obj in objects_to_export:
        asset_name = obj.name
        target_folder = os.path.join(base_path, asset_name)
        export_path = os.path.join(target_folder, asset_name + ".fbx")
        
        print(f"\n--- Processing: {asset_name} ---")
        print(f"  Target folder: {target_folder}")
        print(f"  Export path: {export_path}")
        
        try:
            # フォルダ作成
            os.makedirs(target_folder, exist_ok=True)
            print(f"  Folder created/verified: OK")
            
            # 親と子孫を選択
            obj.select_set(True)
            select_descendants(obj)
            context.view_layer.objects.active = obj
            
            selected_count = len([o for o in context.selected_objects if o.select_get()])
            print(f"  Selected objects (including descendants): {selected_count}")
            
            # FBX書き出し
            print(f"  Starting FBX export...")
            bpy.ops.export_scene.fbx(
                filepath=export_path,
                use_selection=True,
                apply_scale_options='FBX_SCALE_NONE',
                axis_forward='-Z',
                axis_up='Y',
            )
            
            # ファイルが実際に作成されたか確認
            if os.path.exists(export_path):
                file_size = os.path.getsize(export_path)
                print(f"  ✓ Export successful! File size: {file_size} bytes")
                exported_count += 1
            else:
                raise Exception("FBX file was not created")
            
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"  ✗ FAILED to export {asset_name}")
            print(f"  Error: {str(e)}")
            print(f"  Details:\n{error_details}")
            failed_exports.append(f"{asset_name} ({str(e)})")
            
        finally:
            # 選択解除
            obj.select_set(False)
            deselect_descendants(obj)

    # 元の選択状態に戻す
    for obj in original_selection:
        if obj.name in bpy.data.objects:  # オブジェクトがまだ存在するか確認
            obj.select_set(True)
    context.view_layer.objects.active = original_active
    
    print(f"\n=== Export complete ===")
    print(f"Successfully exported: {exported_count} objects")
    print(f"Failed: {len(failed_exports)} objects")
    
    if failed_exports:
        error_msg = f"{len(failed_exports)}件のエクスポートに失敗:\n" + "\n".join(failed_exports)
        return False, error_msg
        
    return True, f"正常に {exported_count} 件のエクスポートが完了しました。"

# --- 2. ボタンの動作 (オペレーター) ---

class WM_OT_ExportCollection(bpy.types.Operator):
    """Exports root objects from a specified collection to FBX."""
    bl_idname = "wm.export_collection"
    bl_label = "Export from Collection"

    def execute(self, context):
        props = context.scene.my_exporter_props
        base_path = props.base_path
        coll_name = props.collection_name

        print(f"\n{'='*50}")
        print(f"EXPORT FROM COLLECTION: {coll_name}")
        print(f"Base Path: {base_path}")
        print(f"{'='*50}")

        if not base_path:
            msg = "Base Path を指定してください。"
            print(f"ERROR: {msg}")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        collection = bpy.data.collections.get(coll_name)
        if not collection:
            msg = f"Collection '{coll_name}' not found."
            print(f"ERROR: {msg}")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        # コレクション配下のすべてのMESH/EMPTYを取得
        objects_in_collection = [obj for obj in collection.all_objects if obj.type in {'MESH', 'EMPTY'}]
        print(f"Objects in collection (MESH/EMPTY): {len(objects_in_collection)}")
        for obj in objects_in_collection:
            print(f"  - {obj.name} (Type: {obj.type}, Parent: {obj.parent.name if obj.parent else 'None'})")
        
        collection_set = set(objects_in_collection)
        
        if not objects_in_collection:
            msg = f"No MESH or EMPTY objects found in '{coll_name}'."
            print(f"WARNING: {msg}")
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        
        # リスト内の「真のルート」のみを set に格納
        root_objects = set()
        for obj in objects_in_collection:
            root = find_root_in_set(obj, collection_set)
            root_objects.add(root)
        
        print(f"Root objects found: {len(root_objects)}")
        for obj in root_objects:
            print(f"  - {obj.name}")
        
        # メインロジックを呼び出す
        success, message = export_objects_logic(context, list(root_objects), base_path)
        
        if success:
            self.report({'INFO'}, message)
        else:
            self.report({'ERROR'}, message)
        
        return {'FINISHED'}

class WM_OT_ExportSelected(bpy.types.Operator):
    """Exports selected root objects (with hierarchy) to FBX."""
    bl_idname = "wm.export_selected"
    bl_label = "Export Selected Objects"

    def execute(self, context):
        props = context.scene.my_exporter_props
        base_path = props.base_path
        
        print(f"\n{'='*50}")
        print(f"EXPORT SELECTED OBJECTS")
        print(f"Base Path: {base_path}")
        print(f"{'='*50}")
        
        if not base_path:
            msg = "Base Path を指定してください。"
            print(f"ERROR: {msg}")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        # 選択中の MESH と EMPTY をすべて取得
        selected_objects = [obj for obj in context.selected_objects if obj.type in {'MESH', 'EMPTY'}]
        print(f"Selected objects (MESH/EMPTY): {len(selected_objects)}")
        for obj in selected_objects:
            print(f"  - {obj.name} (Type: {obj.type}, Parent: {obj.parent.name if obj.parent else 'None'})")
        
        selected_set = set(selected_objects)
        
        if not selected_objects:
            msg = "No selectable MESH or EMPTY objects found."
            print(f"WARNING: {msg}")
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
            
        # 選択セット内の「真のルート」のみを set に格納
        root_objects = set()
        for obj in selected_objects:
            root = find_root_in_set(obj, selected_set)
            root_objects.add(root)
        
        print(f"Root objects found: {len(root_objects)}")
        for obj in root_objects:
            print(f"  - {obj.name}")
            
        # メインロジックを呼び出す
        success, message = export_objects_logic(context, list(root_objects), base_path)
        
        if success:
            self.report({'INFO'}, message)
        else:
            self.report({'ERROR'}, message)

        return {'FINISHED'}

# --- 1. UIの見た目 (パネル) ---
class VIEW3D_PT_MyExporterPanel(bpy.types.Panel):
    bl_label = "Batch FBX Exporter"
    bl_idname = "VIEW3D_PT_my_exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "My Tool"

    def draw(self, context):
        layout = self.layout
        props = context.scene.my_exporter_props
        
        box = layout.box()
        box.label(text="Export Settings:")
        box.prop(props, "base_path")
        
        # パス検証の表示
        if props.base_path:
            if os.path.exists(props.base_path):
                box.label(text="✓ Path exists", icon='CHECKMARK')
            else:
                box.label(text="✗ Path not found", icon='ERROR')

        box = layout.box()
        box.label(text="Export by Collection:")
        box.prop_search(props, "collection_name", bpy.data, "collections", text="Collection")
        box.operator("wm.export_collection", text="Export from Collection")

        box = layout.box()
        box.label(text="Export by Selection:")
        selected_count = len([obj for obj in context.selected_objects if obj.type in {'MESH', 'EMPTY'}])
        box.label(text=f"Selected: {selected_count} objects")
        box.operator("wm.export_selected", text="Export Selected")

# --- 3. UIとデータを結びつける (プロパティ) ---
class MyExporterProperties(bpy.types.PropertyGroup):
    
    base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Root folder to export asset subfolders into",
        subtype='DIR_PATH'
    )
    
    collection_name: bpy.props.StringProperty(
        name="Collection",
        description="Name of the collection to export from"
    )

# --- 5. アドオンの登録・解除 ---
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