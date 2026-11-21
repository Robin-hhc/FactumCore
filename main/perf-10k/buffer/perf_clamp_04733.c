/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04733(unsigned int count)
{
    const unsigned int limit = 42u;
    return count > limit ? limit : count;
}
