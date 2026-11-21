/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04728(unsigned int count)
{
    const unsigned int limit = 206u;
    return count > limit ? limit : count;
}
