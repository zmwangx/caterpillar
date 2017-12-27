.PHONY: qa

qa:
	flake8 caterpillar
	pylint caterpillar
