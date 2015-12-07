#include <sstream>
#include <vector>

namespace deepness
{

struct general_error_t
{
	general_error_t(void);
	general_error_t(general_error_t const &other);
	template <typename whatever_t> general_error_t &operator <<(whatever_t const &input) { buffer << input; return *this; }
	operator std::string(void) const;

	private:
		std::stringstream buffer;
};

inline std::ostream& operator <<(std::ostream &out, general_error_t const &error)
	{ out << static_cast<std::string>(error); return out; }

struct assertion_error_t
{
	assertion_error_t(void);
	assertion_error_t(assertion_error_t const &other);
	template <typename whatever_t> assertion_error_t &operator <<(whatever_t const &input) { buffer << input; return *this; }
	operator std::string(void) const;

	private:
		std::stringstream buffer;
};

inline std::ostream& operator <<(std::ostream &out, assertion_error_t const &error)
	{ out << static_cast<std::string>(error); return out; }

template <typename T> void placement_destroy(T &t) { t.~T(); }

template <typename F> struct finish_t
{
	F f;
	finish_t(F &&f) : f(std::move(f)) {}
	~finish_t(void) { f(); }
};

template <typename F> finish_t<F> finish(F f) { return finish_t<F>(std::move(f)); }

std::string env(std::string const &name, std::string const &suffix = {}, std::string const &def = {});

std::string read_argv(std::vector<std::string> &argv, std::string const &name, bool remove = true);
std::string get_config_path();
std::string read_config(std::string const &name);

}
