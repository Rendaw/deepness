#include <sstream>

struct general_error_t
{
	general_error_t(void) {}
	general_error_t(general_error_t const &other) : buffer(other.buffer.str()) {}
	template <typename whatever_t> general_error_t &operator <<(whatever_t const &input) { buffer << input; return *this; }
	operator std::string(void) const { return buffer.str(); }

	private:
		std::stringstream buffer;
};

inline std::ostream& operator <<(std::ostream &out, general_error_t const &error)
	{ out << static_cast<std::string>(error); return out; }

template <typename T> void placement_destroy(T &t) { t.~T(); }

template <typename F> struct finish_t
{
	F f;
	finish_t(F f) { this->f = std::move(f); }
	~finish_t(void) { f(); }
};

template <typename F> finish_t<F> finish(F f) { return finish_t<F>(std::move(f)); }
