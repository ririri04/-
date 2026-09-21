# note-auto-poster

note.com に投稿した記事の画像から、AI(Claude)が「SNS投稿に最も適した1枚」を自動で選び、
X (Twitter) と Instagram に自動投稿するツールです。

## 仕組み

1. **NoteClient** — note.com の公開API(非公式)から、指定ユーザーの最新記事一覧と
   本文中の画像・アイキャッチ画像を取得します。
2. **ImageSelector** — 取得した画像候補と記事タイトル/概要を Claude (Vision) に渡し、
   視覚的な魅力・内容との関連性・ネタバレ回避などの観点で最も適した画像を1枚選定し、
   X用・Instagram用のキャプション(日本語、ハッシュタグ付き)も生成します。
   `ANTHROPIC_API_KEY` 未設定の場合は先頭の画像を使う簡易フォールバックで動作します。
3. **XPoster** / **InstagramPoster** — 選定した画像とキャプションをそれぞれのAPIで投稿します。
4. **PostedState** — 投稿済みの記事キーを `state.json` に記録し、同じ記事を二重投稿しません。

`note_auto_poster run` を定期実行(cron や GitHub Actions)することで、新しい記事が
公開されるたびに自動でSNS投稿が行われます。

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
| `IG_ACCESS_TOKEN` / `IG_USER_ID` | Instagram Graph API 用。Instagramプロアカウント + 連携したFacebookページが必要 |
| `POST_TO_X` / `POST_TO_INSTAGRAM` | 各投稿先の有効/無効 |
| `MAX_ARTICLES_PER_RUN` | 1回の実行で投稿する記事数の上限 |
| `STATE_FILE` | 投稿済み記事を記録するJSONファイルのパス |
| `DRY_RUN` | `true` で実際には投稿せず選定結果のみログ表示 |

X の認証情報は https://developer.twitter.com/en/portal/dashboard でアプリを作成し、
「Read and Write」権限の Access Token / Secret を発行してください。

Instagram は https://developers.facebook.com/ でMetaアプリを作成し、Instagramプロアカウントを
連携したFacebookページの長期アクセストークンを発行してください。Graph APIの `image_url` は
公開URLである必要がありますが、note の画像は元々公開CDN上にあるためダウンロード/再アップロード
なしでそのまま利用します。

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

`.github/workflows/auto-post.yml` が6時間おきに `run` を実行します。リポジトリの
Settings → Secrets and variables → Actions に、上記の環境変数と同名のシークレットを
登録してください。実行のたびに `state.json` をコミットして投稿済み状態を永続化します。

## テスト

外部API呼び出しはすべてモックしてテストしています。

```bash
pytest
```

## 注意事項

- note.com の非公式APIを利用しているため、note側の仕様変更で動作しなくなる可能性があります。
- 自分が投稿した記事の画像のみを対象にすることを想定しています。他人の記事の画像を無断で
  SNSに転載しないでください。
- X / Instagram それぞれの利用規約・APIレート制限に従って `MAX_ARTICLES_PER_RUN` や
  実行間隔を調整してください。
