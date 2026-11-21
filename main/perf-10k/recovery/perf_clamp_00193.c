/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00193(unsigned int count)
{
    const unsigned int limit = 52u;
    return count > limit ? limit : count;
}
