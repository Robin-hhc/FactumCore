/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00705(unsigned int count)
{
    const unsigned int limit = 41u;
    return count > limit ? limit : count;
}
