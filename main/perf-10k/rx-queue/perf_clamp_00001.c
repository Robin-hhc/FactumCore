/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00001(unsigned int count)
{
    const unsigned int limit = 25u;
    return count > limit ? limit : count;
}
