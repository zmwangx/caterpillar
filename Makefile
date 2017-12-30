.PHONY: dist qa

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

qa:
	flake8 caterpillar
	pylint caterpillar
