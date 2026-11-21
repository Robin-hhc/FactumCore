/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00724(unsigned int count)
{
    const unsigned int limit = 115u;
    return count > limit ? limit : count;
}
