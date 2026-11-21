/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00264(unsigned int count)
{
    const unsigned int limit = 14u;
    return count > limit ? limit : count;
}
