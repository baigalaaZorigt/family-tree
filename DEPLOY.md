# 🚀 Серверт deploy хийх (Docker Compose + PostgreSQL + nginx + Let's Encrypt)

Бүх зүйл `docker compose`-оор ажиллана. Унтрааж асаахад **өгөгдөл алдагдахгүй**
(PostgreSQL → `pgdata` volume, зурагнууд → `./media`). SSL сертификат
**автоматаар** авагдаж, 12 цаг тутам сунгагдана.

## 1. Урьдчилсан бэлтгэл (сервер дээр)
- Ubuntu/Debian сервер, нийтийн IP-тэй.
- **Домэйн** таны серверийн IP рүү заасан байх (DNS `A` бичлэг: `example.com` ба `www.example.com`).
- **80, 443 портууд** нээлттэй (firewall).
- Docker + Docker Compose суулгасан байх:
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```

## 2. Кодыг серверт хуулах
`media/` фолдертойгоо хамт хуул (одоо байгаа зурагнууд хадгалагдана):
```bash
git clone <repo> familytree && cd familytree
# эсвэл scp -r "family tree" user@server:~/familytree
```

## 3. `.env` тохируулах
```bash
cp .env.example .env
nano .env
```
Дараахыг заавал бөглө:
- `DOMAIN`, `EMAIL` — домэйн ба Let's Encrypt-ийн и-мэйл
- `SECRET_KEY` — урт санамсаргүй түлхүүр. Үүсгэх:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` — домэйнээ бич (https://...)
- `POSTGRES_PASSWORD`, `DJANGO_SUPERUSER_PASSWORD` — хүчтэй нууц үг

> 💡 Эхлээд туршихдаа `.env`-д `STAGING=1` болго (Let's Encrypt-ийн хязгаарт баригдахгүй).
> Амжилттай болмогц `STAGING=0` болгоод дахин `./init-letsencrypt.sh` ажиллуул.

## 4. SSL сертификат авах (анх удаа)
```bash
./init-letsencrypt.sh
```
Энэ нь түр сертификат үүсгэж, nginx-г асааж, жинхэнэ Let's Encrypt
сертификатыг авч, reload хийнэ.

## 5. Бүгдийг асаах
```bash
docker compose up -d
```
Эхний ачаалалтад автоматаар:
- PostgreSQL үүснэ
- Миграци хийгдэж **200 хүний эх өгөгдөл** ачаалагдана (`0006_load_full_data`)
- `collectstatic` хийгдэнэ
- Админ superuser үүснэ (`.env`-ийн `DJANGO_SUPERUSER_*`)

Одоо **https://таны-домэйн** нээгдэнэ. Админ: `https://.../admin/`.

> QR кодоо шинэ домэйн (https://...) руу дахин үүсгэхээ мартуузай.

## Хэрэгтэй командууд
```bash
docker compose logs -f web          # лог харах
docker compose ps                   # төлөв
docker compose restart web          # дахин асаах
docker compose down                 # зогсоох (өгөгдөл хэвээр)
docker compose exec web python manage.py createsuperuser   # нэмэлт админ
```

## Шинэчлэлт гаргах

**Автоматаар (санал болгоно):** `main` руу push хийхэд GitHub Actions
(`.github/workflows/deploy.yml`) серверт автоматаар deploy хийнэ —
`git reset --hard origin/main` → `docker compose build web` →
`docker compose up -d --force-recreate web`. Ажиллуулахын тулд repo-ийн
Settings → Secrets and variables → Actions дотор `DEPLOY_HOST`,
`DEPLOY_USER`, `DEPLOY_SSH_KEY` гэсэн 3 secret тохируулсан байх ёстой.
Явцыг GitHub-ийн **Actions** таб дээрээс харна.

**Гараар:**
```bash
git pull
docker compose up -d --build
```

## Өгөгдлийн нөөцлөлт (backup)
```bash
# PostgreSQL
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%F).sql
# Зурагнууд
tar czf media_$(date +%F).tar.gz media/
```

## Бүтэц
| Файл | Үүрэг |
|---|---|
| `Dockerfile` | Django + gunicorn image |
| `docker-compose.yml` | db, web, nginx, certbot |
| `entrypoint.sh` | migrate + collectstatic + gunicorn |
| `nginx/templates/app.conf.template` | nginx (SSL, proxy, static/media) |
| `init-letsencrypt.sh` | SSL-ийг анх удаа авах |
| `.env` | нууц тохиргоо (git-д orno biш) |
