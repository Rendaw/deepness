#include "misc.hxx"

#include <fstream>

namespace deepness
{

general_error_t::general_error_t(void) {}

general_error_t::general_error_t(general_error_t const &other) : buffer(other.buffer.str()) {}

general_error_t::operator std::string(void) const { return buffer.str(); }

std::string read_argv(std::vector<std::string> &argv, std::string const &name, bool remove)
{
	std::string out;
	auto const next = "---" + name;
	auto const prefix = next + "=";
	for (size_t index = 0; index < argv.size(); ++index)
	{
		std::string &current = argv[index];
		if (current.size() < next.size()) continue;
		if (current.substr(0, next.size()) != next) continue;
		if (current.size() == next.size()) 
		{
			if (index + 1 < argv.size()) 
			{
				out = argv[index + 1];
				if (remove) argv.erase(argv.begin() + index + 1);
			}
			if (remove) argv.erase(argv.begin() + index);
			break;
		}
		if (current[next.size()] != '=') continue;
		out = current.substr(next.size() + 1);
		if (remove) argv.erase(argv.begin() + index);
		break;
	}
	return out;
}

std::string env(std::string const &name, std::string const &suffix, std::string const &def)
{
	char *val = getenv(name.c_str());
	if (!val) return def;
	return std::string(val) + suffix;
}

std::string read_config(std::string const &name)
{
	std::ifstream stream
#ifdef _WIN32
		(env("LOCALAPPDATA", {}, env("PROGRAMFILES", {}, "C:/Program Files") + "/deepness/" + name);
#else
		(env("XDG_CONFIG_HOME", {}, env("HOME", "/.config", "/etc")) + "/deepness/" + name);
#endif
	if (!stream) return {};
	std::vector<char> buffer;
	buffer.resize(4096);
	stream.getline(&buffer[0], buffer.size());
	return std::string(&buffer[0], stream.gcount());
}

}

