library_inputs = 
{
	'out/deepness.cxx',
	'out/_deepness.cxx',
	'out/misc.cxx',
}
library_output = 'out/deepness.so'
tup.definerule
{
	inputs = library_inputs,
	outputs = { library_output },
	command = 'g++ -Wall -ggdb -pedantic -std=c++14 -fPIC -shared -Wl,-E -rdynamic -o ' .. library_output .. ' ' .. table.concat(library_inputs, ' '),
}

py_front_inputs = { library_output, 'out/_frontend_py3.cxx' }
py_front_output = 'out/deepness_frontend_python3.so'
tup.definerule
{
	inputs = py_front_inputs,
	outputs = { py_front_output },
	command = 'g++ -Wall -ggdb -pedantic -std=c++14 -fPIC -shared `python3-config --cflags` `python3-config --ldflags` -o ' .. py_front_output .. ' ' .. table.concat(py_front_inputs, ' '),
}

py_back_inputs = { library_output, 'out/_backend_py3.cxx' }
py_back_output = 'out/deepness_backend_python3.so'
tup.definerule
{
	inputs = py_back_inputs,
	outputs = { py_back_output },
	command = 'g++ -Wall -ggdb -pedantic -std=c++14 -fPIC -shared `python3-config --cflags` `python3-config --ldflags` -o ' .. py_back_output .. ' ' .. table.concat(py_back_inputs, ' '),
}
