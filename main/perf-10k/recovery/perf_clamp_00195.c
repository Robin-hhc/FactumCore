/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00195(unsigned int count)
{
    const unsigned int limit = 86u;
    return count > limit ? limit : count;
}
