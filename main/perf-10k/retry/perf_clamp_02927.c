/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02927(unsigned int count)
{
    const unsigned int limit = 216u;
    return count > limit ? limit : count;
}
