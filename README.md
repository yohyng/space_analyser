# Space Analyser

Web カメラ / デバイスのカメラ映像から、空間の状態を **定量指標** としてリアルタイムに解析し、ログとして記録する Web アプリです。

- フロントエンド: React + Vite（カメラ映像の取得・表示、リアルタイム指標のダッシュボード / グラフ表示）
- バックエンド: FastAPI + OpenCV（フレームごとの画像解析、指標算出、ログの永続化）
- 通信: WebSocket でフレーム（JPEG, Base64）を送信し、解析結果を即座に受信

## 構成

```
space_analyser/
├── backend/            FastAPI + OpenCV による解析サーバー
│   ├── app/
│   │   ├── main.py     API / WebSocket エンドポイント
│   │   ├── metrics.py  定量指標の算出ロジック（拡張ポイント）
│   │   └── db.py       SQLite へのログ保存
│   ├── Dockerfile      Railway 等へのデプロイ用
│   ├── railway.json    Railway ビルド/ヘルスチェック設定
│   └── requirements.txt
└── frontend/           React + Vite の Web アプリ
    └── src/
        ├── components/ CameraFeed, MetricsDashboard, MetricsChart, LogHistory
        └── hooks/       useCamera, useAnalysisSocket, useMetricSchema
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

`backend/app/metrics.py` の `FrameAnalyzer` で、フレームごとに以下を算出しています（すべて OpenCV / numpy によるリアルタイム計算）。

| グループ | 指標 |
| --- | --- |
| 照明 | 明るさ（平均輝度）、コントラスト（輝度標準偏差）、ミケルソンコントラスト |
| 画質 | 鮮明度（ラプラシアン分散）、ぼやけ領域の割合、ノイズ推定量 |
| 構造 | エッジ密度、直線検出数（Hough変換）、左右対称性、三分割構図スコア |
| 色彩 | 彩度平均、カラフルさ指数（Hasler–Süsstrunk）、色情報エントロピー、色多様性、平均色（RGB） |
| 動的変化 | 動き量（前フレーム差分）、前景占有率（背景モデル差分） |
| 総合 | 乱雑度指数（上記の一部を統合した簡易スコア） |

指標の一覧・ラベル・単位は `GET /api/metrics/schema` から取得でき、フロントエンドはこれを使って動的に表示を組み立てています。

### 指標を追加するには

1. `backend/app/metrics.py` の `METRIC_DEFINITIONS` にキー・ラベル・単位・説明を追加
2. `FrameAnalyzer.analyze()` で計算し、返り値の dict に同じキーで値を追加

フロントエンドはスキーマを動的に読み込むため、追加のUI改修なしに新しい指標カードが表示されます。

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
