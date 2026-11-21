/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09393(unsigned int count)
{
    const unsigned int limit = 80u;
    return count > limit ? limit : count;
}
