# Space Analyser

Web カメラ / デバイスのカメラ映像から、空間の状態を **定量指標** としてリアルタイムに解析し、ログとして記録する Web アプリです。

- フロントエンド: React + Vite（カメラ映像の取得・表示、指標ごとのスモールマルチプルなグラフ表示）
- バックエンド: FastAPI + KUKAN 決定論的指標コア（`kukan_metrics.py`）＋ OpenCV（フレームの前処理・ログの永続化）
- 通信: WebSocket でフレーム（JPEG, Base64）を送信し、解析結果を即座に受信

## 構成

```
space_analyser/
├── backend/                  FastAPI による解析サーバー
│   ├── app/
│   │   ├── main.py           API / WebSocket エンドポイント
│   │   ├── metrics.py        FrameAnalyzer（前処理・時間依存指標・METRIC_DEFINITIONS）
│   │   ├── kukan_metrics.py  KUKAN 決定論的指標コア（再現性のため無改変で移植）
│   │   └── db.py             SQLite へのログ保存
│   ├── tests/                 test_kukan_metrics.py（参照実装と同一結果になることを検証）
│   ├── Dockerfile            Railway 等へのデプロイ用
│   ├── railway.json          Railway ビルド/ヘルスチェック設定
│   └── requirements.txt
└── frontend/                 React + Vite の Web アプリ
    └── src/
        ├── components/       CameraFeed, MetricsGrid, MetricTile, LogHistory
        └── hooks/            useCamera, useAnalysisSocket, useMetricSchema
```

## セットアップと起動

### バックエンド（Python 3.11+）

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

初回起動時に `backend/data/space_analyser.db`（SQLite）が自動生成されます。

### フロントエンド（Node.js 18+）

```bash
cd frontend
npm install
cp .env.example .env   # 必要に応じて VITE_API_BASE_URL を変更
npm run dev
```

ブラウザで `http://localhost:5173` を開き、「カメラ開始」を押すとカメラへのアクセス許可を求められます。許可すると自動的に解析サーバー（WebSocket）へ接続し、リアルタイムに指標が更新されます。

> カメラ・マイクへのアクセスは HTTPS または `localhost` でのみ許可されます。スマートフォン等の実機で試す場合は HTTPS 経由でアクセスするか、`--host` オプションでのアクセス許可設定を確認してください。

## 算出している定量指標

画像1枚から算出する31指標は **KUKAN 決定論的指標コア**（`kukan-image-first-metrics-1.0.0`）をそのまま採用しています。同じ前処理済み画像を渡せば常に同じ結果になる再現性を優先した仕様で、`backend/app/kukan_metrics.py` は提供されたリファレンス実装を無改変で移植し、`backend/tests/test_kukan_metrics.py` で参照実装と同一の結果になることを検証しています。

前処理は仕様どおり固定です: 最大辺 720px にリサイズ（LANCZOS）、輝度 `Y=0.2126R+0.7152G+0.0722B`、中央差分勾配、暗部/明部/エッジ/高周波の閾値固定、最終値は `0〜1` に clamp して half-up で小数第4位に丸め。

| グループ | 指標 |
| --- | --- |
| 光・明暗 | 平均明度、コントラスト、暗部比率、明部比率、中間調比率 |
| 色彩 | 平均彩度、カラフルネス、色相多様性、暖色比率、寒色比率 |
| 複雑性・テクスチャ | 輝度エントロピー、エッジ密度、エッジ強度、方向多様性、局所テクスチャ変動、高周波成分 |
| 構図・幾何 | 視覚重心X/Y、中心からのズレ、左右/上下バランス、左右/上下対称性、水平垂直軸性 |
| 空間プロキシ | 奥行き手がかり、開放感、囲われ感、前中背景分離、前景重み、背景明るさ、空間明瞭性 |
| 動的変化 | 動き量、前景占有率（前フレーム・背景モデルとの差分。単一画像では再現できないためKUKAN仕様の対象外として別枠で維持） |

各解析結果には `spec_version`（例: `kukan-image-first-metrics-1.0.0`）が付与され、WebSocketの応答・DBログ・CSVエクスポートすべてに保存されます。指標の算出ロジック自体を変更した場合は `SPEC_VERSION` を更新し、過去ログと区別できるようにしてください。

指標の一覧・ラベル・単位は `GET /api/metrics/schema` から取得でき、フロントエンドはこれを使って動的に表示を組み立てています。

### 指標を追加するには

- KUKAN仕様に準じた再現性のある指標を追加する場合: `kukan_metric_spec.json` 相当の定義を追い、`kukan_metrics.py` の `analyze_rgba` に実装（既存の関数は変更しない）
- 時系列・状態依存の指標（今の動き量・前景占有率のような）を追加する場合: `backend/app/metrics.py` の `FrameAnalyzer.analyze()` に追加
- どちらの場合も `backend/app/metrics.py` の `METRIC_DEFINITIONS` にキー・ラベル・単位・説明を追加すれば、フロントエンドはスキーマを動的に読み込むため追加のUI改修なしに新しい指標タイルが表示されます

## ログ

- WebSocket で受信した解析結果は、フロントエンドで「記録する」チェックが有効な場合に `POST` 相当の処理でバックエンドの SQLite に保存されます。
- `GET /api/logs?limit=&session_id=` : ログ一覧の取得
- `GET /api/logs/export.csv?session_id=` : CSV エクスポート
- `GET /api/sessions` : セッション（接続単位）ごとの集計

## デプロイ（Vercel + Railway）

フロントエンドは静的サイトとして Vercel に、バックエンドは WebSocket 常駐プロセスが必要なため Railway にデプロイする構成を想定しています。

### バックエンド（Railway）

1. Railway で `New Project` → `Deploy from GitHub repo` でこのリポジトリを選択
2. サービスの `Settings` → `Root Directory` を `backend` に設定（`backend/Dockerfile` が自動検出されます）
3. `Settings` → `Volumes` で永続ボリュームを追加し、マウントパスを `/data` にする（SQLite のファイルを再デプロイ後も残すため）
4. `Variables` に環境変数を追加
   - `SPACE_ANALYSER_DB_PATH=/data/space_analyser.db`（ボリュームのマウント先に SQLite を保存）
   - `ALLOWED_ORIGINS=https://<vercelのドメイン>`（未設定の場合は `*` で全許可）
5. デプロイ後に発行される公開URL（例: `https://xxxx.up.railway.app`）を控える
   - ヘルスチェックは `/api/health` を使用するよう `railway.json` に設定済み

### フロントエンド（Vercel）

1. Vercel で `New Project` → このリポジトリを選択
2. `Root Directory` を `frontend` に設定（Framework は Vite が自動検出されます）
3. `Environment Variables` に `VITE_API_BASE_URL` として Railway の公開URL（`https://xxxx.up.railway.app`）を設定
4. デプロイ後、Vercel のドメインを Railway 側の `ALLOWED_ORIGINS` に反映して再デプロイ（CORSを絞る場合）

> カメラ利用には HTTPS が必須ですが、Vercel の発行ドメインは標準で HTTPS のためそのまま利用できます。

## 今後の拡張候補

- 物体検出（人・家具など）による点数化
- 深度推定モデルによる奥行き・開放感スコア
- 複数カメラ / 定点観測での経時変化の比較ビュー
- 指標の閾値アラート通知
