# note-auto-poster

note.com に投稿した記事の画像から、AI(Claude)がSNS投稿に適した写真を自動で選び、
X (Twitter) と Instagram に自動投稿するツールです。

## 仕組み

1. **NoteClient** — note.com の公開API(非公式)から、指定ユーザーの最新記事一覧と
   本文中の画像・アイキャッチ画像を取得します。直近の記事で使える写真が尽きた場合は、
   自動でより過去の記事までさかのぼって候補を探します。
2. **ImageSelector** — 取得した画像候補と記事タイトル/概要を Claude (Vision) に渡し、
   視覚的な魅力・内容との関連性・ネタバレ回避などの観点で写真を選定します。
   `ANTHROPIC_API_KEY` 未設定の場合は先頭の画像を使う簡易フォールバックで動作します。
3. **XPoster** — Xには1枚、固定のキャプションで投稿します(`src/note_auto_poster/captions.py`)。
4. **InstagramPoster** — Instagramには同一記事から複数枚(デフォルト5枚)をカルーセル投稿します。
5. **PostedState** — **投稿済みの画像URL**を `state.json` に記録し、同じ写真は二度と使いません
   (記事自体は再利用OK)。また、X/Instagram合わせて直近に使った記事(最大6件)を記録し、
   できるだけ連続で同じ記事にならないようにします。
6. X用とInstagram用は、同じ実行の中で必ず別の記事から選ばれます。
7. **sessions.py** — 「夜撮影会 その④」「夜撮影会 その⑤」のように、記事タイトルの
   「その◯」を除いた部分を「撮影会(セッション)」の単位として扱います。同じ撮影会
   (=同じ衣装)は、当日を含む直近3日間は別の投稿と被らないようにします。

`note_auto_poster run` を定期実行(cron や GitHub Actions)することで、1日数回自動で
SNS投稿が行われます。キャプション文言は `src/note_auto_poster/captions.py` の
`X_CAPTION` / `INSTAGRAM_CAPTION` を直接編集して固定しています。

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
# 開発・テスト用
pip install -r requirements-dev.txt
```

### 2. 環境変数の設定

`.env.example` を `.env` にコピーして値を埋めてください。

```bash
cp .env.example .env
```

| 変数 | 説明 |
| --- | --- |
| `NOTE_USERNAME` | note.com のユーザー名 (`https://note.com/<username>`) |
| `ANTHROPIC_API_KEY` | Claude API キー。未設定でも動作するが画像選定は簡易フォールバックになる |
| `ANTHROPIC_MODEL` | 画像選定に使うモデル(デフォルト `claude-sonnet-5`) |
| `TWITTER_API_KEY` 他 | X Developer Portal で発行する OAuth1.0a の4つのキー(Read/Write権限必須) |
| `IG_ACCESS_TOKEN` / `IG_USER_ID` | Instagram API (Instagramログイン)用。Instagramプロアカウントのみで取得可能(Facebookページ連携は不要) |
| `POST_TO_X` / `POST_TO_INSTAGRAM` | 各投稿先の有効/無効 |
| `INSTAGRAM_IMAGE_COUNT` | Instagramに載せる画像枚数(1記事から選ぶ枚数。デフォルト5) |
| `STATE_FILE` | 投稿済み画像URLを記録するJSONファイルのパス |
| `DRY_RUN` | `true` で実際には投稿せず選定結果のみログ表示 |

X の認証情報は https://developer.twitter.com/en/portal/dashboard でアプリを作成し、
「Read and Write」権限の Access Token / Secret を発行してください。

Instagram は https://developers.facebook.com/ でMetaアプリを作成し、「Instagram API」ユースケース
(Instagramビジネスログイン)を追加してください。Facebookページの連携は不要です。

1. アプリの「役割」タブで自分のInstagramアカウントを「Instagramテスター」として追加し、
   Instagramアプリ側で招待を承認する
2. アプリの「Instagram API」設定画面の「アクセストークンを生成する」からアクセストークンを取得
3. 取得したトークンで以下を実行し、`user_id` を確認する

   ```bash
   curl -s "https://graph.instagram.com/v21.0/me?fields=user_id,username&access_token=<取得したトークン>"
   ```

   返ってきた `user_id` が `IG_USER_ID`、使ったトークンが `IG_ACCESS_TOKEN` です

投稿処理は `graph.instagram.com` の Content Publishing API を使います。`image_url` は公開URLである
必要がありますが、note の画像は元々公開CDN上にあるためダウンロード/再アップロードなしでそのまま
利用します。

### 3. 動作確認

```bash
# 最新記事と画像候補の一覧を表示(投稿なし)
PYTHONPATH=src python -m note_auto_poster.cli list --limit 5

# AIによる選定結果だけを確認(実際には投稿しない)
PYTHONPATH=src python -m note_auto_poster.cli run --dry-run
```

### 4. 実行

```bash
PYTHONPATH=src python -m note_auto_poster.cli run
```

### 5. 自動実行(GitHub Actions)

`.github/workflows/auto-post.yml` が毎日 **6:00 と 20:00(日本時間)** の1日2回 `run` を
実行します。リポジトリの Settings → Secrets and variables → Actions に、上記の環境変数と
同名のシークレットを登録してください。実行のたびに `state.json` をコミットして
投稿済み状態を永続化します。

### キャプションを変更したい場合

`src/note_auto_poster/captions.py` の `X_CAPTION` / `INSTAGRAM_CAPTION` を直接編集して
コミットしてください(AIによる自動生成ではなく固定文言です)。

## テスト

外部API呼び出しはすべてモックしてテストしています。

```bash
pytest
```

## 注意事項

- note.com の非公式APIを利用しているため、note側の仕様変更で動作しなくなる可能性があります。
- 自分が投稿した記事の画像のみを対象にすることを想定しています。他人の記事の画像を無断で
  SNSに転載しないでください。
- X APIは投稿(書き込み)に有料プランへの加入が必要な場合があります。詳細はX Developer Portalで
  ご確認ください。
