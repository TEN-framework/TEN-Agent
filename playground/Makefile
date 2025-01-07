SERVER := ten_agent_playground
cur_dateTime := $(shell date +'%m%d%H%M')
image_address := ghcr.io/ten-framework/${SERVER}:test_${cur_dateTime}
image_address_aws :=  014498659012.dkr.ecr.us-east-1.amazonaws.com/aibum/${SERVER}:test_${cur_dateTime}


#递归删除当前目录下所有临时文件
clean:
	rm -rf .next

build: clean
	docker build -t ${image_address} .

# upload: build
# 	docker build -t ${image_address} .
# 	# docker push ${image_address}
# 	# rm ${SERVER}
# 	# docker rmi ${image_address}

# uploadaws: build
# 	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 014498659012.dkr.ecr.us-east-1.amazonaws.com
# 	docker build -t ${image_address_aws} .
# 	docker push ${image_address_aws}
# 	rm ${SERVER}
# 	docker rmi ${image_address_aws}

# deploy: upload
# 	kubectl set image deployment/${SERVER} ${SERVER}=${image_address}
# 	kubectl rollout status deployment/${SERVER}