bl_info = {
    "name": "Auto UV Seam Unwrap",
    "author": "oimo",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Oimo Tool",
    "description": "円柱・四角柱(ボックス)形状を自動判定してシームを付けUV展開します",
    "category": "UV",
}

import bpy
import bmesh


# ------------------------------------------------------------------------
#   形状判定・シーム付与: 円柱
#   - 上下のキャップ(Ngon or 三角ファン)の境界にシーム
#   - 側面に縦方向の1本シーム
# ------------------------------------------------------------------------
def detect_cylinder(bm):
    """円柱らしき形状なら (キャップ1境界辺, キャップ2境界辺, 側面フェイス一覧) を返す"""
    # Ngonキャップ (Cap Fill Type = Ngon)
    ngon_faces = [f for f in bm.faces if len(f.verts) > 4]
    if len(ngon_faces) == 2 and len(ngon_faces[0].verts) == len(ngon_faces[1].verts):
        cap1, cap2 = ngon_faces
        cap_faces = {cap1, cap2}
        side_faces = [f for f in bm.faces if f not in cap_faces]
        n = len(cap1.verts)
        if len(side_faces) == n and all(len(f.verts) == 4 for f in side_faces):
            return set(cap1.edges), set(cap2.edges), side_faces

    # 三角形ファンキャップ (Cap Fill Type = Triangle Fan)
    poles = []
    for v in bm.verts:
        faces = v.link_faces[:]
        if len(faces) < 3 or len(v.link_edges) != len(faces):
            continue
        if not all(len(f.verts) == 3 for f in faces):
            continue
        n0 = faces[0].normal
        if all(f.normal.dot(n0) > 0.999 for f in faces[1:]):
            poles.append((v, faces))

    if len(poles) == 2 and len(poles[0][1]) == len(poles[1][1]):
        (v1, faces1), (v2, faces2) = poles
        cap_faces = set(faces1) | set(faces2)
        side_faces = [f for f in bm.faces if f not in cap_faces]
        n = len(faces1)
        if len(side_faces) == n and all(len(f.verts) == 4 for f in side_faces):
            edges1 = {e for f in faces1 for e in f.edges if v1 not in e.verts}
            edges2 = {e for f in faces2 for e in f.edges if v2 not in e.verts}
            return edges1, edges2, side_faces

    return None


def find_seed_vertical_edge(cap1_edges, cap2_edges, side_faces):
    """側面から上下キャップの両方に接する「縦方向」の辺を1つ探す"""
    verts1 = {v for e in cap1_edges for v in e.verts}
    verts2 = {v for e in cap2_edges for v in e.verts}
    boundary_edges = cap1_edges | cap2_edges

    for f in side_faces:
        for e in f.edges:
            if e in boundary_edges:
                continue
            v1, v2 = e.verts
            touches_cap1 = (v1 in verts1) or (v2 in verts1)
            touches_cap2 = (v1 in verts2) or (v2 in verts2)
            if touches_cap1 and touches_cap2:
                return e

    # 複数リング構成など: 境界に接しない辺しかない場合のフォールバック
    for f in side_faces:
        for e in f.edges:
            if e not in boundary_edges:
                return e
    return None


def extend_vertical_edge(edge, cap_edges_combined):
    """縦方向の辺を、高さ方向に分割があっても両端まで辺ループとして伸ばす"""
    edges = [edge]
    for start_vert in (edge.verts[0], edge.verts[1]):
        current_edge = edge
        current_vert = start_vert
        while True:
            if current_edge in cap_edges_combined:
                break
            candidates = [e for e in current_vert.link_edges if e is not current_edge]
            if len(candidates) != 3:
                break
            current_faces = set(current_edge.link_faces)
            next_edges = [e for e in candidates if not (set(e.link_faces) & current_faces)]
            if len(next_edges) != 1:
                break
            next_edge = next_edges[0]
            if next_edge in edges:
                break
            edges.append(next_edge)
            current_vert = next_edge.other_vert(current_vert)
            current_edge = next_edge
    return edges


def apply_cylinder_seams(bm, cap1_edges, cap2_edges, side_faces):
    seed = find_seed_vertical_edge(cap1_edges, cap2_edges, side_faces)
    if seed is None:
        return False

    for e in cap1_edges:
        e.seam = True
    for e in cap2_edges:
        e.seam = True
    for e in extend_vertical_edge(seed, cap1_edges | cap2_edges):
        e.seam = True
    return True


# ------------------------------------------------------------------------
#   形状判定・シーム付与: 四角柱(ボックス)
#   - 面隣接グラフの全域木を使い、クロス状の一般的な立方体展開にする
# ------------------------------------------------------------------------
def detect_box(bm):
    """閉じた6枚のクアッドで構成される箱型(立方体・直方体)かどうか"""
    if len(bm.faces) != 6:
        return False
    if not all(len(f.verts) == 4 for f in bm.faces):
        return False
    if not all(len(e.link_faces) == 2 for e in bm.edges):
        return False
    return True


def other_face(edge, face):
    f0, f1 = edge.link_faces
    return f1 if f0 is face else f0


def apply_box_seams(bm):
    faces = list(bm.faces)
    anchor = max(faces, key=lambda f: f.calc_area())

    # アンカー面の辺順で隣接4面を取得(=クロス展開の4方向の腕になる)
    neighbors = []
    hinge_edges = set()
    for e in anchor.edges:
        neighbors.append(other_face(e, anchor))
        hinge_edges.add(e)

    opposite_candidates = [f for f in faces if f is not anchor and f not in neighbors]
    if len(opposite_candidates) != 1:
        return False
    opposite = opposite_candidates[0]

    # 反対面を隣接面の1つに蝶番でつなぎ、腕の先に伸ばす(クロスの尻尾)
    tail_edge = None
    for e in opposite.edges:
        if other_face(e, opposite) is neighbors[0]:
            tail_edge = e
            break
    if tail_edge is None:
        return False
    hinge_edges.add(tail_edge)

    for e in bm.edges:
        e.seam = e not in hinge_edges
    return True


# ------------------------------------------------------------------------
#   オペレーター
# ------------------------------------------------------------------------
class MESH_OT_oimo_auto_uv_seam(bpy.types.Operator):
    """選択したオブジェクトの形状(円柱/四角柱)を自動判定し、シームを付けてUV展開します"""
    bl_idname = "mesh.oimo_auto_uv_seam"
    bl_label = "自動UVシーム展開"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        prev_active = context.view_layer.objects.active
        prev_mode = prev_active.mode if prev_active else 'OBJECT'

        targets = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not targets:
            self.report({'WARNING'}, "メッシュオブジェクトを選択してください")
            return {'CANCELLED'}

        processed = []
        skipped = []

        for obj in targets:
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')

            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()

            for e in bm.edges:
                e.seam = False

            shape = None
            cylinder_result = detect_cylinder(bm)
            if cylinder_result and apply_cylinder_seams(bm, *cylinder_result):
                shape = 'CYLINDER'
            elif detect_box(bm) and apply_box_seams(bm):
                shape = 'BOX'

            bmesh.update_edit_mesh(obj.data)

            if shape is None:
                skipped.append(obj.name)
                bpy.ops.object.mode_set(mode='OBJECT')
                continue

            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.01)
            bpy.ops.uv.pack_islands(margin=0.02)

            bpy.ops.object.mode_set(mode='OBJECT')
            processed.append(obj.name)

        if prev_active:
            context.view_layer.objects.active = prev_active
            if prev_active.mode != prev_mode:
                bpy.ops.object.mode_set(mode=prev_mode)

        if processed:
            self.report({'INFO'}, "UV展開しました: " + ", ".join(processed))
        if skipped:
            self.report({'WARNING'}, "形状を判定できずスキップ: " + ", ".join(skipped))

        if not processed:
            return {'CANCELLED'}
        return {'FINISHED'}


# ------------------------------------------------------------------------
#   UIパネル
# ------------------------------------------------------------------------
class VIEW3D_PT_oimo_auto_uv(bpy.types.Panel):
    """サイドバーに表示されるパネル"""
    bl_label = "自動UVシーム展開"
    bl_idname = "VIEW3D_PT_oimo_auto_uv"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Oimo Tool"

    def draw(self, context):
        layout = self.layout
        layout.label(text="円柱・四角柱を自動判定", icon='UV')
        col = layout.column()
        col.scale_y = 1.5
        col.operator(MESH_OT_oimo_auto_uv_seam.bl_idname, text="自動シーム展開")

        box = layout.box()
        col = box.column(align=True)
        col.label(text="円柱: 上下面+側面1本にシーム")
        col.label(text="四角柱: 一般的な箱型に展開")


# ------------------------------------------------------------------------
#   登録処理
# ------------------------------------------------------------------------
classes = (
    MESH_OT_oimo_auto_uv_seam,
    VIEW3D_PT_oimo_auto_uv,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
