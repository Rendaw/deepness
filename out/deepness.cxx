#include "_deepness.hxx"

#include "misc.hxx"

#include <dlfcn.h>
#include <dirent.h>
#include <fstream>

namespace deepness 
{

static std::vector<std::string> list_dir(std::string path)
{
	DIR *dir;
	std::vector<std::string> out;
	if ((dir = opendir(path.c_str())) != nullptr) 
	{
		struct dirent *entry;
		while ((entry = readdir(dir)) != nullptr) 
		{
			out.push_back(entry->d_name);
		}
		closedir(dir);
	}
	return out;
}

static std::vector<std::string> get_frontend_paths()
{
	return 
	{
		{
#ifdef _WIN32
			env("LOCALAPPDATA", {}) + "/deepness/"
#else
			env("XDG_DATA_HOME", env("HOME", "/.local/share")) + "/deepness/"
#endif
		},
		{
#ifdef _WIN32
			env("PROGRAMFILES", "C:/Program Files") + "/deepness/"
#else
			"/usr/lib/deepness/"
#endif
		}
	};
}

static bool ends_with(std::string const &base, std::string const &suffix) 
{
	if (base.length() < suffix.length()) return false;
	return base.compare(base.length() - suffix.length(), suffix.length(), suffix) == 0;
}

static std::shared_ptr<context_tt> delegate_open(std::string const &path, std::vector<std::string> const &args)
{
#ifdef _WIN32
	HMODULE library = LoadLibrary(path.c_str());
#else
	void *library = dlopen(path.c_str(), RTLD_LAZY);
#endif
	if (library == nullptr)
		throw general_error_t() << "Error loading deepness frontend at [" << path << "]: " << 
#ifdef _WIN32
			GetLastError();
#else
			dlerror();
#endif
#ifdef _WIN32
	FARPROC initializer = GetProcAddress(library, "open");
#else
	void *initializer = dlsym(library, "open");
#endif
	if (initializer == nullptr)
		throw general_error_t() << "Error loading [open] from deepness frontend at [" << path << "]: " << 
#ifdef _WIN32
			GetLastError();
#else
			dlerror();
#endif
	return reinterpret_cast<decltype(deepness::open) *>(initializer)(args);
}

std::shared_ptr<context_tt> open(std::vector<std::string> args)
{
#ifdef _WIN32
	std::string const &suffix = ".dll";
#else
	std::string const &suffix = ".so";
#endif
	if (read_argv(args, "list", false) == "true")
	{
		for (auto const &path : get_frontend_paths())
		{
			for (auto const &file : list_dir(path))
			{
#ifdef _WIN32
				if (!ends_with(file, suffix))
#else
				if (!ends_with(file, suffix))
#endif
					continue;
				std::cout << file.substr(0, file.size() - suffix.size()) << "\n";
				delegate_open(path + file, args);
			}
		}
		return {};
	}
	else
	{
		std::string name = read_argv(args, "frontend");
		if (name.empty()) name = read_config("frontend");
		if (name.empty()) throw general_error_t() << "No specified deepness frontend; You must specify a module.";
		for (auto const &path : get_frontend_paths())
		{
			std::string const full_path = path + name + suffix;
			if (std::ifstream(full_path.c_str()).is_open())
				return delegate_open(full_path, args);
		}
		throw general_error_t() << "No deepness frontend named [" << name << "] found.";
	}
}

}
