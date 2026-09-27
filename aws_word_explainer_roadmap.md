# AWS単語解説Webアプリ 開発ロードマップ

## 目標

入力した単語をGPT APIで解説し、単語・解説・カテゴリをデータベースに保存して、カテゴリ別に表示するWebアプリをAWS上に構築する。

## 完成時の構成

- **ブラウザー**：画面を表示し、APIを呼び出す
- **Route 53**：独自ドメインのDNS設定（独自ドメインを使う場合）
- **CloudFront + AWS WAF**：Webの入口、HTTPS、配信、リクエスト検査
- **S3**：フロントエンドの静的ファイル置き場
- **Application Load Balancer（ALB）**：APIリクエストをEC2へ転送
- **EC2**：アプリケーションのバックエンド処理、GPT API呼び出し
- **RDS for PostgreSQL**：単語・解説・カテゴリの保存
- **AWS Certificate Manager（ACM）**：CloudFrontとALBのTLS証明書
- **AWS Secrets Manager**：GPT APIキーとDB認証情報
- **Amazon CloudWatch**：アプリケーションログとメトリクス
- **AWS CloudTrail**：AWSリソースへの操作記録

本番構成では、RDSをプライベートサブネットに置き、EC2からのみ接続を許可する。EC2をプライベートサブネットに置いて外部のGPT APIへ接続する場合、NAT Gatewayなどの外向き通信経路が必要。NAT Gatewayは費用が発生するため、検証環境の稼働時間と合わせて管理する。

## 進め方

各段階で「動作する成果物」を作り、概念を後から実物と結び付ける。最初から全AWSサービスを同時に設定せず、ローカルアプリ、DB、AWSの順に積み上げる。

| 段階 | 学ぶこと | 作業・成果物 | 完了条件 |
|---|---|---|---|
| 0. 要件と開発準備 | MVP、画面/API/DBの役割、Git | 入力・一覧・カテゴリ表示の画面案、機能一覧、GitHubリポジトリ、README | 最初に作る機能と後回しにする機能が分かれている |
| 1. Webの通信とローカル実装 | HTTP、リクエスト/レスポンス、JSON、ブラウザーとサーバー | ローカルで単語登録APIとカテゴリ別一覧APIを作る。最初はGPT連携なしで固定の解説を保存 | ブラウザーから登録し、一覧に表示できる |
| 2. PostgreSQLとデータ設計 | テーブル、主キー、外部キー、SQL、トランザクション | PostgreSQLに単語・解説・カテゴリを保存。カテゴリが複数付く可能性を考慮し、単語とカテゴリの関係を設計 | SQLで登録・検索・カテゴリ別取得ができる |
| 3. GPT API連携 | APIキー、外部API、タイムアウト、エラー処理、入力検証 | バックエンドからGPT APIを呼び、返答を保存する。キーをソースコードやブラウザーに含めない | APIキーを漏らさず、失敗時に利用者へ適切なエラーを返せる |
| 4. VPCとネットワーク | Region、AZ、VPC、CIDR、サブネット、ルートテーブル、Internet Gateway、Security Group | AWSにVPCを作り、パブリック/プライベートサブネットと通信経路を図示 | 「どの通信が、どこからどこへ、なぜ通るか」を説明できる |
| 5. EC2とRDSの接続 | EC2、OS、プロセス、ポート、DB接続、最小権限 | EC2へバックエンドを配置し、RDS PostgreSQLへ接続。RDSは非公開にし、DBのSecurity GroupはEC2のSecurity GroupからのDBポートだけ許可 | インターネットからRDSへ直接接続できず、アプリ経由で保存・取得できる |
| 6. S3とCloudFront | オブジェクトストレージ、CDN、キャッシュ、オリジン | フロントエンドをS3に置き、CloudFrontから配信。S3への直接公開を避け、CloudFront経由に制限 | CloudFrontのドメインから画面を表示できる |
| 7. ALBとWAF | L7ロードバランサー、ヘルスチェック、HTTPルール、WAFルール | ALBからEC2へAPIを転送し、CloudFrontの /api/* をAPIオリジンへ振り分ける。WAFをCloudFrontに関連付ける | 画面/APIが公開経路から利用でき、WAFのルールがリクエストを検査する |
| 8. 独自ドメインとHTTPS | DNS、TLS証明書、暗号化、証明書とドメインの関係 | 必要ならRoute 53でドメインを設定。ACM証明書をCloudFrontとALBに設定し、HTTPSを強制 | 利用者からCloudFrontまで、CloudFrontからAPIオリジンまでHTTPSで通信する |
| 9. ログ・監視・セキュリティ | ログとメトリクスの違い、アラーム、IAMロール、Secrets Manager、CloudTrail | CloudWatchにアプリログを送り、エラーやCPUなどにアラームを設定。認証情報をSecrets Managerへ移す。CloudTrailの記録を確認 | エラーを調べられ、秘密情報をコードに含めず、AWS操作履歴を確認できる |
| 10. 振り返りと再現性 | バックアップ、復旧、デプロイ、Infrastructure as Code | DBバックアップと復元手順を確認。設定をTerraformまたはAWS CDK等でコード化する | 手順書を見て環境を再作成できる |

## アプリの最小機能

1. 単語を入力する
2. バックエンドで入力を検証する
3. バックエンドからGPT APIに問い合わせる
4. 単語、解説、カテゴリ、作成日時をPostgreSQLに保存する
5. カテゴリを選び、該当する単語と解説を取得する
6. GPT APIやDBが失敗した場合、再試行やエラーメッセージを扱う

ログイン機能、複数ユーザー、編集・削除、検索、タグ付けは、最初のMVPが動いてから追加する。

## 通信経路を理解するための確認表

| 通信元 | 通信先 | 主な目的 | 制御するもの |
|---|---|---|---|
| ブラウザー | CloudFront | 画面/API利用 | HTTPS、WAF |
| CloudFront | S3 | 画面ファイル取得 | CloudFrontからのアクセスに限定 |
| CloudFront | ALB | APIリクエスト転送 | オリジンへのHTTPS、ALBへの到達制限 |
| ALB | EC2 | API処理の転送 | EC2のSecurity GroupでALBからのみ許可 |
| EC2 | RDS | SQL通信 | RDSのSecurity GroupでEC2からのみ許可 |
| EC2 | GPT API | 解説生成 | 外向き通信経路、Secrets ManagerのAPIキー |

## 基本用語の学習順

1. DNSとIPアドレス
2. HTTPとHTTPS、TLS証明書
3. リクエスト/レスポンス、JSON、API
4. ポート番号とTCP
5. VPC、CIDR、サブネット、ルートテーブル
6. Internet GatewayとNAT Gateway
7. Security Groupと最小権限
8. ALBとヘルスチェック
9. DB接続、SQL、バックアップ
10. ログ、メトリクス、アラーム

## コストと安全の運用ルール

- 作業前にAWS Budgetsで予算通知を設定する。
- 学習時は、不要な時間にEC2や検証用リソースを停止・削除する。
- ALB、NAT Gateway、RDS、CloudFront、WAFなどは構成や利用量に応じて費用が発生し得る。作成前に対象リージョンの料金を確認する。
- RDSの停止は恒久的なコスト停止にならない場合があるため、不要な検証環境はバックアップ要否を確認して削除する。
- DBのポートを全インターネット（0.0.0.0/0）に開けない。
- GPT APIキーやDBパスワードをGitHubへコミットしない。
- SSHを広く公開せず、学習環境ではAWS Systems Manager Session Managerの利用も検討する。
- AWSリソースにタグ（例：Project、Environment、Owner）を付け、作成物と費用を追いやすくする。

## 最初の着手項目

- [ ] 画面とAPIの最小要件をREADMEに書く
- [ ] 単語・解説・カテゴリのDB設計を描く
- [ ] ローカルで固定解説による登録・一覧表示を作る
- [ ] PostgreSQLで保存・検索する
- [ ] GPT API連携をバックエンドに追加する
- [ ] AWS Budgetsを設定してからAWSリソースを作成する
