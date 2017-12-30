.PHONY: dist qa flake8 pylint mypy

dist:
	./setup.py sdist
	./setup.py bdist_wheel
	for f in dist/*.tar.gz dist/*.whl; do			\
	  case "$$f" in						\
	    *.dev*)						\
	      ;;						\
	    *)							\
	      test -e "$$f.asc"					\
	        && test "$$f.asc" -nt "$$f"			\
	        || gpg --armor --detach-sign --yes "$$f"	\
	      ;;						\
	  esac							\
	done

qa: flake8 pylint mypy

flake8:
	flake8 src/caterpillar

pylint:
	pylint src/caterpillar

mypy:
	mypy src/caterpillar
