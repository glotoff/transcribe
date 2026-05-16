--BUILD--

docker buildx create --use --name cross-builder

docker buildx build --platform linux/amd64,linux/arm64 -t glotoff/transcribe-bot:latest --push .


--RUN--
docker-compose down &&  docker image prune -f && docker-compose pull && docker-compose up -d --build