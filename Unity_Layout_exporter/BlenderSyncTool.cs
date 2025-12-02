using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement; 
using System.IO;
using System; 

public class BlenderSyncTool : EditorWindow
{
    [MenuItem("Tools/Sync Blender Positions")]
    public static void ShowWindow()
    {
        GetWindow<BlenderSyncTool>("Blender Sync");
    }

    void OnGUI()
    {
        GUILayout.Label("シンプル同期ツール", EditorStyles.boldLabel);
        
        // 現在のモードを表示する
        var prefabStage = PrefabStageUtility.GetCurrentPrefabStage();
        if (prefabStage != null)
        {
            EditorGUILayout.HelpBox($"現在「{prefabStage.prefabContentsRoot.name}」のプレハブを編集中です。\nこのプレハブ内のオブジェクトのみ更新します。", MessageType.Warning);
        }
        else
        {
            EditorGUILayout.HelpBox("シーン全体からオブジェクトを検索して更新します。\n・座標: 小数点第2位\n・X回転: -90固定\n・Z回転: 180固定", MessageType.Info);
        }

        EditorGUILayout.Space();

        if (GUILayout.Button("JSONを読み込んで実行", GUILayout.Height(40)))
        {
            SyncPositions();
        }
    }

    private void SyncPositions()
    {
        string path = EditorUtility.OpenFilePanel("Select layout_data.json", "", "json");
        if (string.IsNullOrEmpty(path)) return;

        string jsonContent = File.ReadAllText(path);
        ObjectList data = JsonUtility.FromJson<ObjectList>(jsonContent);

        if (data == null || data.items == null)
        {
            Debug.LogError("JSON読み込み失敗");
            return;
        }

        int updateCount = 0;
        
        Undo.IncrementCurrentGroup();
        Undo.SetCurrentGroupName("Sync Blender Positions");
        var undoGroup = Undo.GetCurrentGroup();

        // プレハブモードかどうかチェック
        var prefabStage = PrefabStageUtility.GetCurrentPrefabStage();

        foreach (var item in data.items)
        {
            GameObject targetObj = null;

            if (prefabStage != null)
            {
                // --- プレハブモードの場合 ---
                // プレハブのルートオブジェクトを取得し、その中から再帰的に名前で検索する
                GameObject root = prefabStage.prefabContentsRoot;
                targetObj = FindChildRecursively(root.transform, item.name);
            }
            else
            {
                // --- 通常のシーンの場合 ---
                // 従来通りシーン全体から検索
                targetObj = GameObject.Find(item.name);
            }

            if (targetObj != null)
            {
                Undo.RecordObject(targetObj.transform, "Sync Transform");

                // --- 1. 位置 (Position) ---
                float posX = (float)Math.Round(item.position[0], 2);
                float posY = (float)Math.Round(item.position[2], 2);
                float posZ = (float)Math.Round(item.position[1], 2);

                targetObj.transform.localPosition = new Vector3(posX, posY, posZ);

                // --- 2. 回転 (Rotation) ---
                float rotX = -90.0f; 
                float rotY = (float)Math.Round(-item.rotation[2], 2); 
                float rotZ = 180.0f; 

                targetObj.transform.localEulerAngles = new Vector3(rotX, rotY, rotZ);

                updateCount++;
            }
        }
        
        Undo.CollapseUndoOperations(undoGroup);
        Debug.Log($"同期完了: {updateCount} 個のオブジェクトを更新しました");
    }

    // プレハブ内の子要素を再帰的に探すヘルパー関数
    private GameObject FindChildRecursively(Transform parent, string name)
    {
        // まず自分の直下を探す
        Transform result = parent.Find(name);
        if (result != null) return result.gameObject;

        // 見つからなければさらに深く探す
        foreach (Transform child in parent)
        {
            GameObject found = FindChildRecursively(child, name);
            if (found != null) return found;
        }

        return null;
    }

    [System.Serializable]
    public class ObjectList { public ItemData[] items; }

    [System.Serializable]
    public class ItemData
    {
        public string name;
        public float[] position;
        public float[] rotation;
        public float[] scale;
    }
}